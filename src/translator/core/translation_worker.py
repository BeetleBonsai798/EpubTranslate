"""Translation worker for processing chapters."""

import os
import re
import json
import queue
import pypandoc
from PySide6.QtCore import QObject, Signal
from openai import OpenAI
from bs4 import BeautifulSoup

from .context_manager import ContextManager
from .context_filter import ContextFilter
from .prompts import (
    SYSTEM_PROMPT,
    CHARACTER_INSTRUCTION,
    PLACES_INSTRUCTION,
    TERMS_INSTRUCTION,
    NOTES_DETAILED_INSTRUCTION,
    NOTES_MANAGEMENT_INSTRUCTION,
    NOTES_REMINDER,
    BASE_INSTRUCTION,
    ENDING_INSTRUCTION,
    COMPLETE_TRANSLATION_INSTRUCTION
)
from ..utils.token_counter import num_tokens_from_string, split_chapter


class TranslationWorker(QObject):
    """Worker thread for translating chapters."""

    update_progress = Signal(str, int, str)
    finished = Signal(int)
    characters_updated = Signal()
    places_updated = Signal()
    terms_updated = Signal()
    notes_updated = Signal()
    raw_json_updated = Signal(str)
    status_updated = Signal(int, int, int, int)
    chapter_completed = Signal(int)

    def __init__(self, output_folder, model, max_tokens_per_chunk,
                 send_previous, previous_chapters, send_previous_chunks, worker_id,
                 context_mode, notes_mode, power_steering, epub_name, chapter_queue, all_chapters,
                 temperature, max_tokens, frequency_penalty, top_p=1.0, top_k=0, timeout=60.0,
                 providers_list=None, api_key="", epub_book=None, endpoint_config=None,
                 retries_per_provider=1, embedding_config=None):
        super().__init__()
        self.output_folder = output_folder

        # Create xhtml subfolder
        self.xhtml_folder = os.path.join(output_folder, "xhtml")
        os.makedirs(self.xhtml_folder, exist_ok=True)
        self.model = model
        self.max_tokens_per_chunk = max_tokens_per_chunk
        self.send_previous = send_previous
        self.previous_chapters = previous_chapters
        self.send_previous_chunks = send_previous_chunks
        self.worker_id = worker_id
        self._is_running = True
        self.context_mode = context_mode
        self.notes_mode = notes_mode
        self.power_steering = power_steering
        self.epub_name = epub_name
        self.chapter_queue = chapter_queue
        self.all_chapters = all_chapters
        self.epub_book = epub_book

        self.temperature = temperature
        self.max_tokens = max_tokens
        self.frequency_penalty = frequency_penalty
        self.top_p = top_p
        self.top_k = top_k
        self.timeout = timeout
        self.retries_per_provider = retries_per_provider

        # Endpoint configuration
        self.endpoint_config = endpoint_config or {
            'use_custom': False,
            'base_url': "https://openrouter.ai/api/v1",
            'api_key': api_key
        }

        if providers_list and len(providers_list) > 0:
            self.providers = providers_list
        else:
            self.providers = ['targon/fp8', 'lambda/fp8', 'gmicloud/fp8', 'baseten/fp8',
                              'parasail/fp8', 'fireworks', 'chutes/fp8']

        # Initialize context manager
        self.context_manager = ContextManager(
            output_folder, epub_name, context_mode, notes_mode
        )

        # Initialize context filtering support
        self.embedding_config = embedding_config or {'enabled': False}
        self._context_filter = None

        if self.embedding_config.get('enabled', False) and context_mode:
            self._setup_context_filter()

        self.previous_chapter_pairs = []

    def stop(self):
        """Stop the worker."""
        self._is_running = False

    def _setup_context_filter(self):
        self._context_filter = ContextFilter()
        self.context_manager.set_context_filter(self._context_filter, enabled=True)
        self.update_progress.emit(
            "✅ Context filtering enabled (fuzzy text matching)\n",
            self.worker_id, "green"
        )

    def run(self):
        """Main worker loop."""
        try:
            while self._is_running and not self.chapter_queue.empty():
                try:
                    chapter_number, chapter = self.chapter_queue.get_nowait()
                except queue.Empty:
                    break

                self.translate_chapter(chapter_number, chapter)
                self.chapter_queue.task_done()

            self.finished.emit(self.worker_id)
        except Exception as e:
            self.update_progress.emit(f"Error: {str(e)}", self.worker_id, "red")
            self.finished.emit(self.worker_id)

    def load_previous_chapters(self, chapter_number):
        """Load previous chapters for context."""
        self.previous_chapter_pairs = []
        if not self.send_previous or self.previous_chapters <= 0:
            return

        start_chapter = max(1, chapter_number - self.previous_chapters)
        for i in range(start_chapter, chapter_number):
            if i >= 1 and i <= len(self.all_chapters):
                original_chapter = self.all_chapters[i - 1]

                # Preprocess to convert SVG images to regular img tags
                original_chapter = self._preprocess_svg_images(original_chapter)

                # Convert to markdown for consistency
                original_markdown = pypandoc.convert_text(
                    original_chapter,
                    'markdown',
                    format='html',
                    extra_args=['--wrap=preserve']
                )

                # Load translated XHTML instead of DOCX
                translated_file = os.path.join(self.xhtml_folder, f"{i}.xhtml")
                if os.path.exists(translated_file):
                    try:
                        with open(translated_file, 'r', encoding='utf-8') as f:
                            translated_xhtml = f.read()

                        # Preprocess to convert SVG images to regular img tags
                        translated_xhtml = self._preprocess_svg_images(translated_xhtml)

                        # Convert to markdown for context
                        translated_markdown = pypandoc.convert_text(
                            translated_xhtml,
                            'markdown',
                            format='html',
                            extra_args=['--wrap=preserve']
                        )

                        self.previous_chapter_pairs.append({
                            'chapter_number': i,
                            'original': original_markdown.strip(),
                            'translated': translated_markdown.strip()
                        })

                        self.update_progress.emit(
                            f"✓ Loaded previous chapter {i} for context\n",
                            self.worker_id,
                            "green"
                        )
                    except Exception as e:
                        self.update_progress.emit(
                            f"⚠ Error reading previous chapter {i}: {str(e)}\n",
                            self.worker_id,
                            "orange"
                        )

        if self.previous_chapter_pairs:
            self.update_progress.emit(
                f"📚 Using {len(self.previous_chapter_pairs)} previous chapters for context\n",
                self.worker_id,
                "blue"
            )

    def _preprocess_svg_images(self, xhtml_content):
        """
        Preprocess XHTML to convert SVG elements with embedded images to regular img tags.

        This prevents pandoc from converting images to base64-encoded data URLs in markdown.
        Instead, SVG images are converted to simple <img> tags that reference the actual image files.

        Handles:
        - SVG with single embedded image -> converts to <img>
        - SVG with multiple embedded images -> converts to multiple <img> tags
        - SVG with actual vector graphics (no <image> tags) -> leaves unchanged
        - Regular <img> tags -> leaves unchanged
        """
        soup = BeautifulSoup(xhtml_content, 'xml')

        # Find all SVG elements
        for svg in soup.find_all('svg'):
            # Look for image elements inside the SVG (could be multiple)
            image_elems = svg.find_all('image')

            # Only process SVGs that contain embedded images
            if image_elems:
                # Use empty alt text to avoid pandoc creating figure/figcaption
                # (the desc URLs are just source credits, not useful for readers)
                alt_text = ''

                # If there's only one image, replace with a single img tag
                if len(image_elems) == 1:
                    image_elem = image_elems[0]
                    if image_elem.get('xlink:href'):
                        image_src = image_elem['xlink:href']

                        # Create a new img tag with empty alt to prevent figcaption
                        img_tag = soup.new_tag('img', src=image_src, alt=alt_text)

                        # Extract width/height if present for better sizing control
                        width = image_elem.get('width')
                        height = image_elem.get('height')
                        if width and height:
                            # Add as style to maintain aspect ratio with CSS max-width
                            img_tag['style'] = f'max-width: 100%; height: auto;'

                        # Replace the SVG with the img tag
                        svg.replace_with(img_tag)

                # If there are multiple images, replace with a div containing multiple img tags
                else:
                    container = soup.new_tag('div')
                    for image_elem in image_elems:
                        if image_elem.get('xlink:href'):
                            image_src = image_elem['xlink:href']
                            img_tag = soup.new_tag('img', src=image_src, alt=alt_text)
                            img_tag['style'] = 'max-width: 100%; height: auto;'
                            container.append(img_tag)

                    if container.contents:  # Only replace if we created any img tags
                        svg.replace_with(container)

        return str(soup)

    def translate_chapter(self, chapter_number, chapter):
        """Translate a single chapter."""
        self.load_previous_chapters(chapter_number)

        # Preprocess to convert SVG images to regular img tags
        chapter = self._preprocess_svg_images(chapter)

        # Convert XHTML to Markdown using pypandoc
        chapter_markdown = pypandoc.convert_text(
            chapter,
            'markdown',
            format='html',
            extra_args=['--wrap=preserve']
        )

        chunks = split_chapter(chapter_markdown, max_tokens=self.max_tokens_per_chunk)
        total_chunks = len(chunks)
        translated_chunks = []
        all_chunks_successful = True

        self.status_updated.emit(self.worker_id, chapter_number, 0, total_chunks)

        current_chapter_chunks = []
        current_chapter_translations = []

        for i, chunk in enumerate(chunks, start=1):
            if not self._is_running:
                all_chunks_successful = False
                break

            self.status_updated.emit(self.worker_id, chapter_number, i, total_chunks)

            chunk_tokens = num_tokens_from_string(chunk, 'cl100k_base')
            self.update_progress.emit(
                f"\n--- Translating Chapter {chapter_number}, Chunk {i}/{total_chunks} ({chunk_tokens} tokens) ---\n",
                self.worker_id,
                "black"
            )

            translated_chunk = self.translate_chunk(chunk, current_chapter_chunks, current_chapter_translations)

            if translated_chunk is None:
                all_chunks_successful = False
                break

            translated_chunks.append(translated_chunk)

            if self.send_previous_chunks:
                current_chapter_chunks.append(chunk)
                current_chapter_translations.append(translated_chunk)

        if all_chunks_successful and self._is_running and len(translated_chunks) == len(chunks):
            self.status_updated.emit(self.worker_id, chapter_number, total_chunks, total_chunks)

            self.create_xhtml_chapter(chapter_number, translated_chunks, chapter)

            self.update_progress.emit(
                f"\n\n✅ Chapter {chapter_number} completed successfully!\n",
                self.worker_id,
                "green"
            )

            self.chapter_completed.emit(chapter_number)
        else:
            self.update_progress.emit(
                f"\n\n❌ Chapter {chapter_number} translation failed or incomplete. File not created.\n",
                self.worker_id,
                "red"
            )

    def _preserve_blank_lines(self, text):
        """
        Preserve multiple consecutive blank lines by inserting &nbsp; on empty lines.

        Pandoc collapses runs of blank lines into a single paragraph break.
        To preserve multiple blank paragraphs, we need to insert non-breaking spaces.

        This matches the behavior of your HTML-to-markdown converter where:
        - Single \n = line break within paragraph
        - Double \n\n = new paragraph
        - Triple+ \n\n\n = blank paragraphs between content
        """
        import re

        # Find sequences of 3+ newlines (which means 2+ blank lines)
        # and insert &nbsp; on the empty lines to force blank paragraphs
        def replace_blank_lines(match):
            newline_count = len(match.group(0))
            # First \n\n creates paragraph break, rest need &nbsp; markers
            # Each additional pair of \n\n should become a blank paragraph
            blank_paragraphs_needed = (newline_count - 2) // 2
            return '\n\n' + ('\n\n&nbsp;\n\n' * blank_paragraphs_needed)

        # Replace runs of 3 or more newlines
        text = re.sub(r'\n{3,}', replace_blank_lines, text)
        return text

    def create_xhtml_chapter(self, chapter_number, translated_chunks, original_xhtml):
        """Create XHTML file from translated markdown."""
        try:
            # Combine all translated chunks
            full_translation = '\n\n'.join(translated_chunks)

            # Preserve multiple consecutive blank lines
            full_translation = self._preserve_blank_lines(full_translation)

            # Convert markdown → XHTML using pypandoc
            xhtml_body = pypandoc.convert_text(
                full_translation,
                'html',
                format='markdown',
                extra_args=['--wrap=preserve']
            )

            # Parse original XHTML to extract structure using XML parser
            from bs4 import XMLParsedAsHTMLWarning
            import warnings
            warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
            
            soup = BeautifulSoup(original_xhtml, 'xml')

            # Replace body content with translated content
            body = soup.find('body')
            if body:
                body.clear()
                # Parse translated content with HTML parser (not XML) because pandoc generates multiple root elements
                translated_soup = BeautifulSoup(xhtml_body, 'html.parser')

                # Extract content from the translated HTML body
                translated_body = translated_soup.find('body')
                if translated_body:
                    for child in list(translated_body.children):
                        body.append(child)
                else:
                    # If no body tag, just append the content
                    for child in list(translated_soup.children):
                        body.append(child)

            # Update language attributes from source language to English
            html_tag = soup.find('html')
            if html_tag:
                if html_tag.get('xml:lang'):
                    html_tag['xml:lang'] = 'en'
                if html_tag.get('lang'):
                    html_tag['lang'] = 'en'

            # Save to file with proper XML declaration
            output_file = os.path.join(self.xhtml_folder, f"{chapter_number}.xhtml")
            with open(output_file, 'w', encoding='utf-8') as f:
                # Write with XML declaration
                f.write(str(soup))

            self.update_progress.emit(
                f"✅ Created XHTML file: {output_file}\n",
                self.worker_id, "green"
            )

        except Exception as e:
            self.update_progress.emit(
                f"❌ Error creating XHTML for chapter {chapter_number}: {str(e)}\n",
                self.worker_id, "red"
            )
            import traceback
            traceback.print_exc()

    def extract_json_from_response(self, response_text):
        """Extract JSON data from API response."""
        try:
            json_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_blocks:
                return json.loads(json_blocks[-1])

            json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            return None
        except json.JSONDecodeError as e:
            self.update_progress.emit(f"\nJSON Parse Error: {str(e)}\n", self.worker_id, "red")
            return None

    def translate_chunk(self, chunk, current_chapter_chunks, current_chapter_translations):
        """Translate a single chunk of text."""
        if not self.endpoint_config['api_key']:
            self.update_progress.emit("❌ Error: No API key provided\n", self.worker_id, "red")
            return None

        client = OpenAI(api_key=self.endpoint_config['api_key'])
        client.base_url = self.endpoint_config['base_url']

        # Build the base messages with conditional JSON instruction placement
        base_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        # Add context prompts based on enabled modes (with filtering if available)
        if self.context_mode:
            if self.context_manager.context_filter_enabled:
                char_prompt, place_prompt, terms_prompt, match_details = self.context_manager.get_all_relevant_prompts(chunk)

                total_chars_db = len(self.context_manager.characters)
                total_places_db = len(self.context_manager.places)
                total_terms_db = len(self.context_manager.terms)

                found_chars = len(match_details['characters'])
                found_places = len(match_details['places'])
                found_terms = len(match_details['terms'])

                self.update_progress.emit(
                    f"🔍 Context Filter: {found_chars}/{total_chars_db} chars, "
                    f"{found_places}/{total_places_db} places, "
                    f"{found_terms}/{total_terms_db} terms\n",
                    self.worker_id, "blue"
                )

                if match_details['characters']:
                    char_info = ", ".join([f"{orig}→{trans} ['{matched}' {mtype}]"
                                          for orig, trans, matched, mtype in match_details['characters'][:5]])
                    self.update_progress.emit(f"  📌 Chars: {char_info}\n", self.worker_id, "blue")

                if match_details['places']:
                    place_info = ", ".join([f"{orig}→{trans} ['{matched}' {mtype}]"
                                           for orig, trans, matched, mtype in match_details['places'][:5]])
                    self.update_progress.emit(f"  📍 Places: {place_info}\n", self.worker_id, "blue")

                if match_details['terms']:
                    term_info = ", ".join([f"{orig}→{trans} ['{matched}' {mtype}]"
                                          for orig, trans, matched, mtype in match_details['terms'][:5]])
                    self.update_progress.emit(f"  ⚔️ Terms: {term_info}\n", self.worker_id, "blue")

            else:
                char_prompt = self.context_manager.get_character_prompt()
                place_prompt = self.context_manager.get_place_prompt()
                terms_prompt = self.context_manager.get_terms_prompt()

            if char_prompt:
                base_messages.append({"role": "user", "content": char_prompt})
            if place_prompt:
                base_messages.append({"role": "user", "content": place_prompt})
            if terms_prompt:
                base_messages.append({"role": "user", "content": terms_prompt})

        if self.notes_mode:
            notes_prompt = self.context_manager.get_notes_prompt()
            if notes_prompt:
                base_messages.append({"role": "user", "content": notes_prompt})

        # Add previous chapters context
        if self.send_previous and self.previous_chapter_pairs:
            self.update_progress.emit(f"📖 Including {len(self.previous_chapter_pairs)} previous chapters as context\n",
                                      self.worker_id, "blue")
            for prev_chapter in self.previous_chapter_pairs:
                base_messages.append({
                    "role": "user",
                    "content": f"PREVIOUS CHAPTER {prev_chapter['chapter_number']} (for context only):\n{prev_chapter['original']}"
                })
                base_messages.append({
                    "role": "assistant",
                    "content": json.dumps({
                        "complete_translation": prev_chapter['translated']
                    }, ensure_ascii=False)
                })

        # Add current chapter's previous chunks for immediate context
        if self.send_previous_chunks and current_chapter_chunks:
            self.update_progress.emit(
                f"🔗 Including {len(current_chapter_chunks)} previous chunks from current chapter\n",
                self.worker_id, "blue")
            for prev_chunk, prev_trans in zip(current_chapter_chunks, current_chapter_translations):
                base_messages.append({
                    "role": "user",
                    "content": f"CURRENT CHAPTER - PREVIOUS PART:\n{prev_chunk}"
                })
                base_messages.append({
                    "role": "assistant",
                    "content": json.dumps({
                        "complete_translation": prev_trans
                    }, ensure_ascii=False)
                })

        # Build instruction
        instruction, json_format_instruction, context_notes_system_instruction = self._build_instruction()

        # If power_steering is disabled, add JSON format and context/notes instructions to system prompt
        # If power_steering is enabled, they stay in the user instruction (default behavior)
        if not self.power_steering:
            system_additions = ""
            if context_notes_system_instruction:
                system_additions += "\n\n" + context_notes_system_instruction
            system_additions += "\n\n" + json_format_instruction
            base_messages[0]["content"] = base_messages[0]["content"] + system_additions

        # Add current chunk to translate
        base_messages.extend([
            # {"role": "user", "content": instruction},
            {"role": "user", "content": f"CURRENT CHAPTER - TEXT TO TRANSLATE:\n```[START]\n{chunk}\n```[END]"},
            {"role": "user", "content": instruction},
        ])

        # Attempt translation with provider fallback
        return self._attempt_translation(base_messages)

    def _build_instruction(self):
        """Build comprehensive instruction for translation."""
        # Create the JSON schema based on enabled modes
        json_schema = {}

        # Only include context fields if context_mode is enabled
        if self.context_mode:
            json_schema["characters"] = [
                {
                    "original": "original_name",
                    "translated": "translated_name",
                    "gender": "male/female/not_clear"
                }
            ]
            json_schema["places"] = [
                {
                    "original": "original_place",
                    "translated": "translated_place"
                }
            ]
            json_schema["terms"] = [
                {
                    "original": "original_term",
                    "translated": "translated_term",
                    "category": "spell/weapon/skill/technique/ability/item/artifact/race/other"
                }
            ]

        # Only include notes if notes_mode is enabled
        if self.notes_mode:
            json_schema["notes"] = [
                {
                    "action": "add/update/delete",
                    "key": "short_identifier",
                    "note": "brief_note_content (not needed for delete action)"
                }
            ]

        # Always include complete_translation
        json_schema["complete_translation"] = "the_translated_text_here"

        # Build the comprehensive instruction
        instruction_parts = []
        context_notes_instruction_parts = []  # For power steering
        instruction_number = 1

        # Context mode instructions - only add if enabled
        if self.context_mode:
            character_instruction = CHARACTER_INSTRUCTION.format(number=instruction_number)
            instruction_parts.append(character_instruction)
            context_notes_instruction_parts.append(character_instruction)
            instruction_number += 1

            places_instruction = PLACES_INSTRUCTION.format(number=instruction_number)
            instruction_parts.append(places_instruction)
            context_notes_instruction_parts.append(places_instruction)
            instruction_number += 1

            terms_instruction = TERMS_INSTRUCTION.format(number=instruction_number)
            instruction_parts.append(terms_instruction)
            context_notes_instruction_parts.append(terms_instruction)
            instruction_number += 1

        # Refined notes mode instructions - only add if enabled
        if self.notes_mode:
            notes_detailed_instruction = NOTES_DETAILED_INSTRUCTION.format(number=instruction_number)
            instruction_parts.append(notes_detailed_instruction)
            context_notes_instruction_parts.append(notes_detailed_instruction)
            instruction_number += 1

        complete_translation_instr = COMPLETE_TRANSLATION_INSTRUCTION.format(number=instruction_number)
        instruction_parts.append(complete_translation_instr)
        context_notes_instruction_parts.append(complete_translation_instr)

        notes_instruction = ""
        if self.notes_mode:
            notes_instruction = NOTES_MANAGEMENT_INSTRUCTION
            context_notes_instruction_parts.append(notes_instruction)

        # JSON format instruction - this will be conditionally placed
        notes_reminder = ""
        if self.notes_mode:
            notes_reminder = NOTES_REMINDER

        json_format_instruction = (
            f"Respond in utf-8 encoding with ONLY a VALID JSON object in this format:\n"
            f"```json\n{json.dumps(json_schema, indent=2, ensure_ascii=False)}\n```\n"
            f"{notes_reminder}"
        )

        # Build context and notes instructions for system prompt (when power steering enabled)
        context_notes_system_instruction = ""
        if context_notes_instruction_parts:
            context_notes_system_instruction = (
                f"ALWAYS list in this EXACT ORDER:\n"
                f"{''.join(context_notes_instruction_parts)}\n"
            )

        # Build the full instruction
        # If power_steering is enabled, include JSON format and context/notes instructions in user instruction (default behavior)
        # If power_steering is disabled, exclude them from user instruction (they go in system prompt)
        if self.power_steering:
            full_instruction = (
                BASE_INSTRUCTION +
                f"ALWAYS list in this EXACT ORDER:\n"
                f"{''.join(instruction_parts)}\n"
                f"{notes_instruction}\n"
                f"{json_format_instruction}\n"
                f"{ENDING_INSTRUCTION}"
            )
        else:
            full_instruction = BASE_INSTRUCTION + ENDING_INSTRUCTION

        return full_instruction, json_format_instruction, context_notes_system_instruction

    def _attempt_translation(self, base_messages):
        """Attempt translation with provider fallback and per-provider retries."""
        # Determine retry logic based on endpoint type
        if self.endpoint_config['use_custom']:
            # Custom endpoint - use retries_per_provider
            provider_list = [None]
        else:
            # OpenRouter with providers
            provider_list = self.providers

        # Iterate through each provider
        for provider_index, current_provider in enumerate(provider_list):
            if not self._is_running:
                break

            # Try each provider up to retries_per_provider times
            for retry_attempt in range(self.retries_per_provider):
                if not self._is_running:
                    break

                attempt_num = retry_attempt + 1
                if current_provider:
                    self.update_progress.emit(
                        f"\n🔄 Provider {provider_index + 1}/{len(provider_list)}: {current_provider} - Attempt {attempt_num}/{self.retries_per_provider}\n",
                        self.worker_id, "blue"
                    )
                else:
                    self.update_progress.emit(
                        f"\n🔄 Custom endpoint - Attempt {attempt_num}/{self.retries_per_provider}\n",
                        self.worker_id, "blue"
                    )

                # Create a fresh copy of base messages for this attempt
                messages_for_provider = [msg.copy() for msg in base_messages]

                # Clean up any openrouter-specific stuff that might interfere
                for msg in messages_for_provider:
                    msg.pop('prefix', None)
                # print(messages_for_provider)

                try:
                    # print(messages_for_provider)
                    # Build request parameters
                    request_params = {
                        'model': self.model,
                        'messages': messages_for_provider,
                        'temperature': self.temperature,
                        'stream': True,
                        'max_tokens': self.max_tokens,
                        'frequency_penalty': self.frequency_penalty,
                        'top_p': self.top_p,
                    }

                    # Initialize extra_body if needed
                    extra_body = {}

                    # Add top_k to extra_body if not 0 (0 means disabled)
                    if self.top_k > 0:
                        extra_body['top_k'] = self.top_k

                    # Only add provider routing for OpenRouter
                    if not self.endpoint_config['use_custom'] and current_provider:
                        extra_body['provider'] = {
                            'order': [current_provider],
                            'allow_fallbacks': False
                        }

                    # Add extra_body to request_params if it has any content
                    if extra_body:
                        request_params['extra_body'] = extra_body

                    client = OpenAI(api_key=self.endpoint_config['api_key'])
                    client.base_url = self.endpoint_config['base_url']

                    # Add extra headers for OpenRouter
                    extra_headers = {}
                    if 'openrouter.ai' in self.endpoint_config['base_url']:
                        extra_headers = {
                            "HTTP-Referer": "https://github.com/BeetleBonsai798/EpubTranslate",
                            "X-Title": "EpubTranslate"
                        }

                    stream = client.chat.completions.create(
                        timeout=self.timeout,
                        extra_headers=extra_headers if extra_headers else None,
                        **request_params
                    )

                    # Collect response from this provider/endpoint
                    current_response = ""
                    chunk_count = 0

                    try:
                        for chunk_data in stream:
                            if not self._is_running:
                                break

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
                                        current_response += content
                                        self.update_progress.emit(content, self.worker_id, "blue")
                                else:
                                    continue

                            except (AttributeError, IndexError, TypeError):
                                continue

                    except Exception as stream_error:
                        self.update_progress.emit(
                            f"\n⚠️ Stream error: {str(stream_error)}, but may have received complete response\n",
                            self.worker_id, "orange"
                        )

                    # Log how many chunks were processed
                    if chunk_count > 0:
                        self.update_progress.emit(
                            f"\n📊 Processed {chunk_count} stream chunks\n",
                            self.worker_id, "blue"
                        )

                    # Try to parse the complete response
                    json_data = self.extract_json_from_response(current_response)

                    if json_data and 'complete_translation' in json_data:
                        if current_provider:
                            self.update_progress.emit(
                                f"\n✅ Successfully got response from provider: {current_provider}\n",
                                self.worker_id, "green"
                            )
                        else:
                            self.update_progress.emit(
                                f"\n✅ Successfully got response from custom endpoint\n",
                                self.worker_id, "green"
                            )

                        # Emit the raw JSON response
                        self.raw_json_updated.emit(current_response)

                        # Update all lists based on enabled modes
                        if self.context_mode:
                            context_updated = False
                            if 'characters' in json_data:
                                self.context_manager.update_characters(json_data['characters'])
                                self.characters_updated.emit()
                                context_updated = True
                            if 'places' in json_data:
                                self.context_manager.update_places(json_data['places'])
                                self.places_updated.emit()
                                context_updated = True
                            if 'terms' in json_data:
                                self.context_manager.update_terms(json_data['terms'])
                                self.terms_updated.emit()

                        if self.notes_mode and 'notes' in json_data:
                            self.context_manager.update_notes(
                                json_data['notes'],
                                update_callback=lambda msg: self.update_progress.emit(f"{msg}\n", self.worker_id, "blue")
                            )
                            self.notes_updated.emit()

                        return json_data['complete_translation']

                    # If we didn't get valid JSON, retry or move to next provider
                    if retry_attempt < self.retries_per_provider - 1:
                        # Still have retries left for this provider
                        if current_provider:
                            retry_notice = f"\n⚠️ Invalid JSON response from {current_provider}, retrying same provider...\n"
                        else:
                            retry_notice = f"\n⚠️ Invalid JSON response from custom endpoint, retrying...\n"
                        self.update_progress.emit(retry_notice, self.worker_id, "orange")
                    else:
                        # No more retries for this provider, will move to next
                        if current_provider and provider_index < len(provider_list) - 1:
                            retry_notice = f"\n⚠️ Invalid JSON response from {current_provider} after {self.retries_per_provider} attempts, moving to next provider...\n"
                            self.update_progress.emit(retry_notice, self.worker_id, "orange")

                except Exception as e:
                    error_source = current_provider if current_provider else "custom endpoint"
                    self.update_progress.emit(
                        f"\n❌ Error with {error_source}: {str(e)}\n",
                        self.worker_id, "red"
                    )

                    # Check if we should retry or move to next provider
                    if retry_attempt < self.retries_per_provider - 1:
                        self.update_progress.emit(f"🔄 Retrying same provider...\n", self.worker_id, "orange")
                    elif provider_index < len(provider_list) - 1:
                        self.update_progress.emit(f"🔄 Moving to next provider...\n", self.worker_id, "orange")

        # All attempts failed
        if self.endpoint_config['use_custom']:
            self.update_progress.emit(
                f"\n\n💥 ERROR: Failed to get valid translation from custom endpoint after {self.retries_per_provider} attempts.\n",
                self.worker_id, "red"
            )
        else:
            total_attempts = len(self.providers) * self.retries_per_provider
            self.update_progress.emit(
                f"\n\n💥 ERROR: Failed to get valid translation after {total_attempts} total attempts "
                f"({self.retries_per_provider} retries per provider).\n"
                f"Providers tried: {', '.join(self.providers)}\n",
                self.worker_id, "red"
            )
        return None
