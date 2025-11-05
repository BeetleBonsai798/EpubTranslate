"""TOC translation worker for processing table of contents with context."""

import json
import re
from PySide6.QtCore import QObject, Signal
from openai import OpenAI
from ebooklib import epub
from bs4 import BeautifulSoup

from .context_manager import ContextManager


class TocTranslationWorker(QObject):
    """Worker for translating TOC entries with context awareness."""

    update_progress = Signal(str, str)
    raw_json_updated = Signal(str)
    finished = Signal(bool, str)
    toc_item_translated = Signal(int, int, str, str)

    def __init__(self, original_book, translated_xhtml_map, context_manager, endpoint_config,
                 batch_size=30, providers_list=None, temperature=0.3, max_tokens=2000,
                 frequency_penalty=0.0, top_p=1.0, top_k=0, timeout=60.0, retries_per_provider=1):
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

        # Provider settings
        if providers_list and len(providers_list) > 0:
            self.providers = providers_list
        else:
            self.providers = ['deepseek/deepseek-v3.2-exp']

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
        # Build context prompts
        char_context = self.context_manager.get_character_prompt()
        place_context = self.context_manager.get_place_prompt()
        terms_context = self.context_manager.get_terms_prompt()
        notes_context = self.context_manager.get_notes_prompt()

        # Build batch translation request
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

        if not api_key:
            self.update_progress.emit("❌ Error: No API key configured", "red")
            return None

        provider_index = 0
        attempts = 0
        max_total_attempts = len(self.providers) * self.retries_per_provider

        while attempts < max_total_attempts:
            if not self._is_running:
                return None

            current_provider = self.providers[provider_index]
            model = f"{current_provider}/{self.endpoint_config['model']}" if '/' not in self.endpoint_config['model'] else self.endpoint_config['model']

            try:
                self.update_progress.emit(f"🔄 Calling API with provider: {current_provider}, model: {model}", "yellow")
                self.update_progress.emit(f"   Attempt {(attempts % self.retries_per_provider) + 1}/{self.retries_per_provider} for this provider", "yellow")

                client = OpenAI(api_key=api_key, base_url=base_url, timeout=self.timeout)

                # Build API parameters
                api_params = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "stream": True
                }

                # Add optional parameters if not default
                if self.frequency_penalty != 0.0:
                    api_params["frequency_penalty"] = self.frequency_penalty
                if self.top_p != 1.0:
                    api_params["top_p"] = self.top_p
                if self.top_k != 0:
                    api_params["top_k"] = self.top_k

                # Try to use JSON mode if available
                try:
                    api_params["response_format"] = {"type": "json_object"}
                except Exception:
                    pass

                # Add extra headers for OpenRouter
                extra_headers = {}
                if 'openrouter.ai' in base_url:
                    extra_headers = {
                        "HTTP-Referer": "https://github.com/BeetleBonsai798/EpubTranslate",
                        "X-Title": "EpubTranslate"
                    }

                if extra_headers:
                    api_params["extra_headers"] = extra_headers

                response_stream = client.chat.completions.create(**api_params)

                # Stream response with robust error handling
                response_text = ""
                chunk_count = 0
                self.update_progress.emit("\n[STREAMING RESPONSE]:", "cyan")

                try:
                    for chunk_data in response_stream:
                        if not self._is_running:
                            return None

                        chunk_count += 1

                        # Handle different streaming formats safely
                        try:
                            if (hasattr(chunk_data, 'choices') and
                                    chunk_data.choices is not None and
                                    len(chunk_data.choices) > 0):

                                choice = chunk_data.choices[0]

                                if (hasattr(choice, 'delta') and
                                        choice.delta is not None and
                                        hasattr(choice.delta, 'content') and
                                        choice.delta.content is not None):
                                    content = choice.delta.content
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

                # Log how many chunks were processed
                if chunk_count > 0:
                    self.update_progress.emit(
                        f"\n📊 Processed {chunk_count} stream chunks\n",
                        "white"
                    )

                self.update_progress.emit("\n" + "="*80 + "\n", "green")

                # Clean and parse response
                cleaned_response = self.clean_json_response(response_text)

                # Emit raw JSON for display
                self.raw_json_updated.emit(cleaned_response)

                # Parse response
                parsed = json.loads(cleaned_response)

                if 'translations' not in parsed:
                    self.update_progress.emit("⚠️ Warning: Response missing 'translations' field", "orange")
                    raise ValueError("Response missing 'translations' field")

                self.update_progress.emit(f"✅ Successfully parsed {len(parsed['translations'])} translations", "green")
                return parsed['translations']

            except json.JSONDecodeError as e:
                self.update_progress.emit(f"❌ JSON Parse Error: {str(e)}", "red")
                self.update_progress.emit(f"   Raw response: {response_text[:200]}...", "red")
                attempts += 1

                if attempts % self.retries_per_provider == 0:
                    provider_index = (provider_index + 1) % len(self.providers)
                    self.update_progress.emit(f"🔄 Moving to next provider: {self.providers[provider_index]}", "orange")
                else:
                    self.update_progress.emit(f"🔄 Retrying with same provider...", "orange")

            except Exception as e:
                self.update_progress.emit(f"❌ API Error: {str(e)}", "red")
                attempts += 1

                if attempts % self.retries_per_provider == 0:
                    provider_index = (provider_index + 1) % len(self.providers)
                    if attempts < max_total_attempts:
                        self.update_progress.emit(f"🔄 Moving to next provider: {self.providers[provider_index]}", "orange")
                else:
                    self.update_progress.emit(f"🔄 Retrying with same provider...", "orange")

        self.update_progress.emit(f"❌ All retry attempts exhausted after {max_total_attempts} tries", "red")
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
