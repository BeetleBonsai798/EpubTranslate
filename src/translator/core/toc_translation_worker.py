"""TOC translation worker for processing table of contents with context."""

import json
import re
from PySide6.QtCore import QObject, Signal
from openai import OpenAI
from ebooklib import epub
from bs4 import BeautifulSoup

from ..config import DEFAULT_PROVIDERS
from .context_manager import ContextManager
from .context_filter import ContextFilter


class TocTranslationWorker(QObject):
    """Worker for translating TOC entries with context awareness."""

    update_progress = Signal(str, str)
    raw_json_updated = Signal(str)
    finished = Signal(bool, str)
    toc_item_translated = Signal(int, int, str, str)

    def __init__(self, original_book, translated_xhtml_map, context_manager, endpoint_config,
                 batch_size=30, providers_list=None, temperature=0.3, max_tokens=2000,
                 frequency_penalty=0.0, top_p=1.0, top_k=0, timeout=60.0, retries_per_provider=1,
                 embedding_config=None, reasoning_config=None, json_output_mode='off'):
        super().__init__()
        self.original_book = original_book
        self.translated_xhtml_map = translated_xhtml_map
        self.context_manager = context_manager
        self.endpoint_config = endpoint_config
        self.batch_size = batch_size
        self._is_running = True

        # Translation settings
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.frequency_penalty = frequency_penalty
        self.top_p = top_p
        self.top_k = top_k
        self.timeout = timeout
        self.retries_per_provider = retries_per_provider

        # Reasoning + JSON-output configuration
        self.reasoning_config = reasoning_config or {
            'enabled': False,
            'effort': 'medium',
            'max_tokens': 0,
            'exclude': False,
        }
        self.json_output_mode = json_output_mode

        # Context filtering
        self.embedding_config = embedding_config or {'enabled': False}
        self._context_filter = None
        if self.embedding_config.get('enabled', False):
            self._setup_context_filter()

        # Provider settings
        if providers_list and len(providers_list) > 0:
            self.providers = providers_list
        else:
            self.providers = list(DEFAULT_PROVIDERS)

    def _setup_context_filter(self):
        self._context_filter = ContextFilter()
        filter_chars = self.embedding_config.get('filter_characters', False)
        filter_places = self.embedding_config.get('filter_places', True)
        filter_terms = self.embedding_config.get('filter_terms', True)

        self.context_manager.set_context_filter(
            self._context_filter,
            enabled=True,
            filter_characters=filter_chars,
            filter_places=filter_places,
            filter_terms=filter_terms
        )

    def stop(self):
        """Stop the worker."""
        self._is_running = False

    def clean_json_response(self, response_text):
        """Clean JSON response by removing markdown code blocks and other artifacts."""
        # Remove markdown code blocks
        response_text = re.sub(r'^```json\s*', '', response_text, flags=re.MULTILINE)
        response_text = re.sub(r'^```\s*$', '', response_text, flags=re.MULTILINE)
        response_text = re.sub(r'^```\s*', '', response_text, flags=re.MULTILINE)

        # Strip whitespace
        response_text = response_text.strip()

        return response_text

    def extract_context(self, href):
        """Extract context from TOC link location."""
        if '#' in href:
            file_path, anchor_id = href.split('#', 1)
        else:
            file_path = href
            anchor_id = None

        if file_path not in self.translated_xhtml_map:
            return None

        xhtml = self.translated_xhtml_map[file_path]
        soup = BeautifulSoup(xhtml, 'lxml')

        target = soup.find(id=anchor_id) if anchor_id else soup.find('body')
        if not target:
            return None

        # Get heading
        heading_elem = target.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        heading = heading_elem.get_text(strip=True) if heading_elem else None

        # Get context paragraphs
        paragraphs = []
        current = target
        for _ in range(3):
            next_p = current.find_next('p')
            if next_p:
                paragraphs.append(next_p.get_text(strip=True))
                current = next_p

        return {
            'heading': heading,
            'context': '\n'.join(paragraphs)
        }

    def collect_toc_items(self, toc_item, items_list):
        """Recursively collect all TOC items."""
        if isinstance(toc_item, epub.Link):
            items_list.append(toc_item)
        elif isinstance(toc_item, tuple):
            section, children = toc_item
            if isinstance(section, epub.Link):
                items_list.append(section)
            for child in children:
                self.collect_toc_items(child, items_list)

    def translate_batch(self, toc_items, batch_start, batch_end):
        """Translate a batch of TOC items using the API with provider rotation and retries."""
        # Build batch translation request first so we can use the text for filtering
        batch_items = []
        for i in range(batch_start, batch_end):
            item = toc_items[i]
            context = self.extract_context(item.href)

            item_data = {
                'index': i,
                'original': item.title,
                'href': item.href
            }

            if context:
                item_data['heading'] = context['heading']
                item_data['context_preview'] = context['context'][:200] if context['context'] else ""

            batch_items.append(item_data)

        # Build combined text for context filtering
        batch_text_parts = []
        for item_data in batch_items:
            batch_text_parts.append(item_data.get('original', ''))
            if 'heading' in item_data and item_data['heading']:
                batch_text_parts.append(item_data['heading'])
            if 'context_preview' in item_data and item_data['context_preview']:
                batch_text_parts.append(item_data['context_preview'])
        batch_text = '\n'.join(batch_text_parts)

        # Build context prompts (with filtering if enabled)
        if self.context_manager.context_filter_enabled:
            char_context, place_context, terms_context, match_details = self.context_manager.get_all_relevant_prompts(batch_text)

            total_chars = len(self.context_manager.characters)
            total_places = len(self.context_manager.places)
            total_terms = len(self.context_manager.terms)
            matched_chars = len(match_details.get('characters', []))
            matched_places = len(match_details.get('places', []))
            matched_terms = len(match_details.get('terms', []))

            self.update_progress.emit(
                f"🔍 Context filter: chars {matched_chars}/{total_chars}, "
                f"places {matched_places}/{total_places}, "
                f"terms {matched_terms}/{total_terms}",
                "cyan"
            )
        else:
            char_context = self.context_manager.get_character_prompt()
            place_context = self.context_manager.get_place_prompt()
            terms_context = self.context_manager.get_terms_prompt()

        notes_context = self.context_manager.get_notes_prompt()

        # Build prompt
        from .prompts import TOC_SYSTEM_PROMPT
        system_prompt = TOC_SYSTEM_PROMPT

        user_prompt = ""

        if char_context:
            user_prompt += char_context
        if place_context:
            user_prompt += place_context
        if terms_context:
            user_prompt += terms_context
        if notes_context:
            user_prompt += notes_context

        user_prompt += "\n\nTOC Entries to Translate:\n"
        user_prompt += json.dumps(batch_items, ensure_ascii=False, indent=2)
        user_prompt += "\n\nProvide translations in JSON format."

        # Debug: Print the request
        self.update_progress.emit("\n" + "="*80, "blue")
        self.update_progress.emit(f"[DEBUG] Translating TOC batch {batch_start+1}-{batch_end} of {len(toc_items)}", "blue")
        self.update_progress.emit("="*80, "blue")
        self.update_progress.emit("\n[SYSTEM PROMPT]:", "cyan")
        self.update_progress.emit(system_prompt, "white")
        self.update_progress.emit("\n[USER PROMPT]:", "cyan")
        self.update_progress.emit(user_prompt, "white")
        self.update_progress.emit("="*80 + "\n", "blue")

        # Provider rotation with retries
        api_key = self.endpoint_config['api_key']
        base_url = self.endpoint_config['base_url']
        endpoint_type = self.endpoint_config.get('endpoint_type', 'openrouter')
        model_id = self.endpoint_config.get('model', '')

        if not api_key:
            self.update_progress.emit("❌ Error: No API key configured", "red")
            return None

        # OpenRouter rotates through configured providers; DeepSeek and Custom
        # have a single upstream so we just retry on `None`.
        if endpoint_type == 'openrouter':
            provider_list = self.providers
        else:
            provider_list = [None]

        endpoint_label = {
            'openrouter': 'OpenRouter',
            'deepseek': 'DeepSeek',
            'custom': 'custom endpoint',
        }.get(endpoint_type, endpoint_type)

        last_response_text = ""

        for provider_index, current_provider in enumerate(provider_list):
            if not self._is_running:
                return None

            for retry_attempt in range(self.retries_per_provider):
                if not self._is_running:
                    return None

                attempt_num = retry_attempt + 1
                if current_provider:
                    self.update_progress.emit(
                        f"🔄 Provider {provider_index + 1}/{len(provider_list)}: {current_provider} - Attempt {attempt_num}/{self.retries_per_provider}",
                        "yellow"
                    )
                else:
                    self.update_progress.emit(
                        f"🔄 {endpoint_label} - Attempt {attempt_num}/{self.retries_per_provider}",
                        "yellow"
                    )

                response_text = ""
                reasoning_text = ""

                try:
                    client = OpenAI(api_key=api_key, base_url=base_url, timeout=self.timeout)

                    api_params = {
                        "model": model_id,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "stream": True
                    }

                    if self.frequency_penalty != 0.0:
                        api_params["frequency_penalty"] = self.frequency_penalty
                    if self.top_p != 1.0:
                        api_params["top_p"] = self.top_p

                    extra_body = {}
                    if self.top_k != 0:
                        extra_body['top_k'] = self.top_k

                    reasoning_enabled = self.reasoning_config.get('enabled', False)

                    if endpoint_type == 'openrouter':
                        if current_provider:
                            extra_body['provider'] = {
                                'order': [current_provider],
                                'allow_fallbacks': False
                            }
                        if reasoning_enabled:
                            r = {}
                            if self.reasoning_config.get('max_tokens', 0) > 0:
                                r['max_tokens'] = self.reasoning_config['max_tokens']
                            else:
                                r['effort'] = self.reasoning_config.get('effort', 'medium')
                            if self.reasoning_config.get('exclude'):
                                r['exclude'] = True
                            extra_body['reasoning'] = r
                    elif endpoint_type == 'deepseek':
                        if reasoning_enabled:
                            extra_body['thinking'] = {'type': 'enabled'}
                            api_params['reasoning_effort'] = self.reasoning_config.get('effort', 'high')
                        else:
                            extra_body['thinking'] = {'type': 'disabled'}

                    # TOC translation depends on JSON parsing; default to json_object
                    # whenever the user hasn't asked for json_schema strict mode.
                    if self.json_output_mode == 'json_schema' and endpoint_type == 'openrouter':
                        api_params['response_format'] = {
                            'type': 'json_schema',
                            'json_schema': {
                                'name': 'toc_translations',
                                'strict': True,
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'translations': {
                                            'type': 'array',
                                            'items': {
                                                'type': 'object',
                                                'properties': {
                                                    'index': {'type': 'integer'},
                                                    'translated': {'type': 'string'},
                                                },
                                                'required': ['index', 'translated'],
                                                'additionalProperties': False,
                                            },
                                        },
                                    },
                                    'required': ['translations'],
                                    'additionalProperties': False,
                                },
                            },
                        }
                    else:
                        api_params['response_format'] = {'type': 'json_object'}

                    if extra_body:
                        api_params['extra_body'] = extra_body

                    if endpoint_type == 'openrouter':
                        api_params['extra_headers'] = {
                            "HTTP-Referer": "https://github.com/BeetleBonsai798/EpubTranslate",
                            "X-Title": "EpubTranslate"
                        }

                    response_stream = client.chat.completions.create(**api_params)

                    chunk_count = 0
                    reasoning_started = False
                    content_started = False
                    self.update_progress.emit("\n[STREAMING RESPONSE]:", "cyan")

                    try:
                        for chunk_data in response_stream:
                            if not self._is_running:
                                return None

                            chunk_count += 1

                            try:
                                if (hasattr(chunk_data, 'choices') and
                                        chunk_data.choices is not None and
                                        len(chunk_data.choices) > 0):

                                    choice = chunk_data.choices[0]

                                    if hasattr(choice, 'delta') and choice.delta is not None:
                                        reasoning_chunk = (
                                            getattr(choice.delta, 'reasoning_content', None)
                                            or getattr(choice.delta, 'reasoning', None)
                                        )
                                        if reasoning_chunk:
                                            if not reasoning_started:
                                                self.update_progress.emit("\n💭 [REASONING]\n", "gray")
                                                reasoning_started = True
                                            reasoning_text += reasoning_chunk
                                            self.update_progress.emit(reasoning_chunk, "gray")

                                        content = getattr(choice.delta, 'content', None)
                                        if content:
                                            if reasoning_started and not content_started:
                                                self.update_progress.emit("\n📝 [RESPONSE]\n", "white")
                                                content_started = True
                                            response_text += content
                                            self.update_progress.emit(content, "white")
                                else:
                                    continue

                            except (AttributeError, IndexError, TypeError):
                                continue

                    except Exception as stream_error:
                        self.update_progress.emit(
                            f"\n⚠️ Stream error: {str(stream_error)}, but may have received complete response\n",
                            "orange"
                        )

                    if chunk_count > 0:
                        self.update_progress.emit(
                            f"\n📊 Processed {chunk_count} stream chunks\n",
                            "white"
                        )

                    self.update_progress.emit("\n" + "="*80 + "\n", "green")

                    last_response_text = response_text

                    cleaned_response = self.clean_json_response(response_text)

                    if reasoning_text:
                        combined_raw = (
                            "--- REASONING ---\n"
                            f"{reasoning_text}\n\n"
                            "--- RESPONSE ---\n"
                            f"{cleaned_response}"
                        )
                    else:
                        combined_raw = cleaned_response
                    self.raw_json_updated.emit(combined_raw)

                    parsed = json.loads(cleaned_response)

                    if 'translations' not in parsed:
                        self.update_progress.emit("⚠️ Warning: Response missing 'translations' field", "orange")
                        raise ValueError("Response missing 'translations' field")

                    self.update_progress.emit(
                        f"✅ Successfully parsed {len(parsed['translations'])} translations", "green"
                    )
                    return parsed['translations']

                except json.JSONDecodeError as e:
                    self.update_progress.emit(f"❌ JSON Parse Error: {str(e)}", "red")
                    self.update_progress.emit(f"   Raw response: {last_response_text[:200]}...", "red")
                    if retry_attempt < self.retries_per_provider - 1:
                        self.update_progress.emit("🔄 Retrying same provider...", "orange")
                    elif provider_index < len(provider_list) - 1:
                        next_provider = provider_list[provider_index + 1]
                        self.update_progress.emit(
                            f"🔄 Moving to next provider: {next_provider}",
                            "orange"
                        )

                except Exception as e:
                    self.update_progress.emit(f"❌ API Error: {str(e)}", "red")
                    if retry_attempt < self.retries_per_provider - 1:
                        self.update_progress.emit("🔄 Retrying same provider...", "orange")
                    elif provider_index < len(provider_list) - 1:
                        next_provider = provider_list[provider_index + 1]
                        self.update_progress.emit(
                            f"🔄 Moving to next provider: {next_provider}",
                            "orange"
                        )

        max_total_attempts = len(provider_list) * self.retries_per_provider
        self.update_progress.emit(
            f"❌ All retry attempts exhausted after {max_total_attempts} tries",
            "red"
        )
        return None

    def translate_toc_item(self, item, translations_map):
        """Recursively translate TOC items using the translations map."""
        if isinstance(item, epub.Link):
            # Look up translation in map
            translated_title = translations_map.get(item.href, {}).get('translated', item.title)
            return epub.Link(item.href, translated_title, item.uid)
        elif isinstance(item, tuple):
            section, children = item
            return (
                self.translate_toc_item(section, translations_map),
                [self.translate_toc_item(c, translations_map) for c in children]
            )
        return item

    def run(self):
        """Main worker loop."""
        try:
            self.update_progress.emit("\n🔄 Starting TOC Translation...\n", "blue")

            # Collect all TOC items
            all_toc_items = []
            for item in self.original_book.toc:
                self.collect_toc_items(item, all_toc_items)

            total_items = len(all_toc_items)
            self.update_progress.emit(f"📚 Found {total_items} TOC entries to translate\n", "blue")

            if total_items == 0:
                self.update_progress.emit("✅ No TOC entries found, skipping translation", "green")
                self.finished.emit(True, "No TOC entries to translate")
                return

            # Create translations map
            translations_map = {}

            # Process in batches
            for batch_start in range(0, total_items, self.batch_size):
                if not self._is_running:
                    self.update_progress.emit("⏹️ TOC translation stopped by user", "orange")
                    self.finished.emit(False, "Stopped by user")
                    return

                batch_end = min(batch_start + self.batch_size, total_items)

                self.update_progress.emit(
                    f"\n📦 Processing batch: {batch_start+1}-{batch_end} of {total_items}\n",
                    "yellow"
                )

                translations = self.translate_batch(all_toc_items, batch_start, batch_end)

                if translations:
                    for trans_item in translations:
                        idx = trans_item.get('index')
                        translated = trans_item.get('translated', '')

                        if idx is not None and 0 <= idx < total_items:
                            original_item = all_toc_items[idx]
                            translations_map[original_item.href] = {
                                'original': original_item.title,
                                'translated': translated
                            }

                            # Emit progress
                            self.toc_item_translated.emit(
                                idx + 1,
                                total_items,
                                original_item.title,
                                translated
                            )

                            self.update_progress.emit(
                                f"✓ [{idx+1}/{total_items}] {original_item.title} → {translated}",
                                "green"
                            )
                else:
                    self.update_progress.emit(
                        f"⚠️ Batch translation failed, using original titles",
                        "orange"
                    )

            # Apply translations to TOC
            self.update_progress.emit("\n🔧 Applying translations to TOC structure...\n", "blue")
            new_toc = [self.translate_toc_item(item, translations_map) for item in self.original_book.toc]
            self.original_book.toc = tuple(new_toc)

            self.update_progress.emit("\n✅ TOC Translation Complete!\n", "green")
            self.finished.emit(True, f"Translated {total_items} TOC entries")

        except Exception as e:
            self.update_progress.emit(f"\n❌ Error in TOC translation: {str(e)}\n", "red")
            import traceback
            self.update_progress.emit(traceback.format_exc(), "red")
            self.finished.emit(False, str(e))
