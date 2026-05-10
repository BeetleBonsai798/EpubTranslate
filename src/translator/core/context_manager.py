"""Context management for characters, places, terms, and translation notes."""

import json
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .context_filter import ContextFilter

logger = logging.getLogger(__name__)


def format_character_name(char_data: Dict) -> str:
    """Format a character entry's name parts into a single display string.

    Produces strings like "first=Taro, middle=Mary, last=Tanaka" — omitting
    middle/last when absent so single-given-name characters render as just
    "first=Sakura".
    """
    parts = [f"first={char_data.get('first_name', '')}"]

    middle_names = char_data.get('middle_names') or []
    if middle_names:
        parts.append(f"middle={' '.join(middle_names)}")

    last_name = char_data.get('last_name', '')
    if last_name:
        parts.append(f"last={last_name}")

    return ", ".join(parts)


class ContextManager:
    """Manages translation context including characters, places, terms, and notes.

    Provides persistent storage and retrieval of translation consistency information
    to maintain uniform character names, place names, and specialized terminology
    across an entire EPUB translation project.
    """

    # Valid gender values for characters
    VALID_GENDERS = {'male', 'female', 'not_clear'}

    # Valid categories for specialized terms
    VALID_TERM_CATEGORIES = {
        'spell', 'weapon', 'skill', 'technique', 'ability',
        'item', 'artifact', 'other'
    }

    def __init__(
        self,
        output_folder: str,
        epub_name: str,
        context_mode: bool = False,
        notes_mode: bool = False
    ):
        """Initialize context manager.

        Args:
            output_folder: Base output directory for translated files
            epub_name: Name of the EPUB being translated
            context_mode: Enable character/place/term tracking
            notes_mode: Enable translation notes tracking
        """
        self.output_folder = Path(output_folder)
        self.epub_name = epub_name
        self.context_mode = context_mode
        self.notes_mode = notes_mode

        # Create context subfolder
        self.context_folder = self.output_folder / "context"
        self.context_folder.mkdir(parents=True, exist_ok=True)

        # Define context file paths
        self.character_file = self.context_folder / f"{epub_name}_characters.json"
        self.place_file = self.context_folder / f"{epub_name}_places.json"
        self.terms_file = self.context_folder / f"{epub_name}_terms.json"
        self.notes_file = self.context_folder / f"{epub_name}_notes.json"

        # Load existing context data
        self.characters: OrderedDict[str, Dict[str, str]] = self.load_characters()
        self.places: OrderedDict[str, str] = self.load_places()
        self.terms: OrderedDict[str, Dict[str, str]] = self.load_terms()
        self.notes: OrderedDict[str, str] = self.load_notes()

        self._context_filter: Optional['ContextFilter'] = None
        self._use_context_filter: bool = False
        self._filter_characters: bool = False
        self._filter_places: bool = True
        self._filter_terms: bool = True

    def load_characters(self) -> OrderedDict[str, Dict[str, str]]:
        """Load character translations from file.

        Returns:
            OrderedDict mapping original names to translation data
        """
        if not self.context_mode or not self.character_file.exists():
            return OrderedDict()

        try:
            with open(self.character_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            char_dict = OrderedDict(data)
            logger.info(f"Loaded {len(char_dict)} characters from {self.character_file}")
            return char_dict

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in character file: {e}", exc_info=True)
            return OrderedDict()
        except Exception as e:
            logger.error(f"Error loading characters: {e}", exc_info=True)
            return OrderedDict()

    def load_places(self) -> OrderedDict[str, str]:
        """Load place translations from file.

        Returns:
            OrderedDict mapping original place names to translations
        """
        if not self.context_mode or not self.place_file.exists():
            return OrderedDict()

        try:
            with open(self.place_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            logger.info(f"Loaded {len(data)} places from {self.place_file}")
            return OrderedDict(data)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in place file: {e}", exc_info=True)
            return OrderedDict()
        except Exception as e:
            logger.error(f"Error loading places: {e}", exc_info=True)
            return OrderedDict()

    def load_terms(self) -> OrderedDict[str, Dict[str, str]]:
        """Load specialized term translations from file.

        Returns:
            OrderedDict mapping original terms to translation data
        """
        if not self.context_mode or not self.terms_file.exists():
            return OrderedDict()

        try:
            with open(self.terms_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            terms_dict = OrderedDict(data)
            logger.info(f"Loaded {len(terms_dict)} terms from {self.terms_file}")
            return terms_dict

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in terms file: {e}", exc_info=True)
            return OrderedDict()
        except Exception as e:
            logger.error(f"Error loading terms: {e}", exc_info=True)
            return OrderedDict()

    def load_notes(self) -> OrderedDict[str, str]:
        """Load translation notes from file.

        Returns:
            OrderedDict mapping note keys to note text
        """
        if not self.notes_mode or not self.notes_file.exists():
            return OrderedDict()

        try:
            with open(self.notes_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            logger.info(f"Loaded {len(data)} notes from {self.notes_file}")
            return OrderedDict(data)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in notes file: {e}", exc_info=True)
            return OrderedDict()
        except Exception as e:
            logger.error(f"Error loading notes: {e}", exc_info=True)
            return OrderedDict()

    def save_characters(self) -> bool:
        """Save character translations to file.

        Returns:
            True if successful, False otherwise
        """
        if not self.context_mode:
            return True

        try:
            with open(self.character_file, 'w', encoding='utf-8') as f:
                json.dump(dict(self.characters), f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(self.characters)} characters to {self.character_file}")
            return True
        except IOError as e:
            logger.error(f"IO error saving character file: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Error saving character file: {e}", exc_info=True)
            return False

    def save_places(self) -> bool:
        """Save place translations to file.

        Returns:
            True if successful, False otherwise
        """
        if not self.context_mode:
            return True

        try:
            with open(self.place_file, 'w', encoding='utf-8') as f:
                json.dump(dict(self.places), f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(self.places)} places to {self.place_file}")
            return True
        except IOError as e:
            logger.error(f"IO error saving place file: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Error saving place file: {e}", exc_info=True)
            return False

    def save_terms(self) -> bool:
        """Save specialized term translations to file.

        Returns:
            True if successful, False otherwise
        """
        if not self.context_mode:
            return True

        try:
            with open(self.terms_file, 'w', encoding='utf-8') as f:
                json.dump(dict(self.terms), f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(self.terms)} terms to {self.terms_file}")
            return True
        except IOError as e:
            logger.error(f"IO error saving terms file: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Error saving terms file: {e}", exc_info=True)
            return False

    def save_notes(self) -> bool:
        """Save translation notes to file.

        Returns:
            True if successful, False otherwise
        """
        if not self.notes_mode:
            return True

        try:
            with open(self.notes_file, 'w', encoding='utf-8') as f:
                json.dump(dict(self.notes), f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(self.notes)} notes to {self.notes_file}")
            return True
        except IOError as e:
            logger.error(f"IO error saving notes file: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Error saving notes file: {e}", exc_info=True)
            return False

    def update_characters(self, characters_data: List[Dict]) -> None:
        """Update character list with new data.

        Args:
            characters_data: List of character dicts with 'original', 'first_name',
                'middle_names' (list), 'last_name', and 'gender'.
        """
        if not self.context_mode or not characters_data:
            return

        added = 0
        updated = 0

        for char_info in characters_data:
            if not isinstance(char_info, dict):
                continue

            if 'original' not in char_info or 'first_name' not in char_info:
                continue

            orig = char_info['original'].strip()
            first_name = char_info['first_name'].strip()
            last_name = char_info.get('last_name', '').strip()

            middle_raw = char_info.get('middle_names', []) or []
            if not isinstance(middle_raw, list):
                middle_raw = []
            middle_names = [
                m.strip() for m in middle_raw
                if isinstance(m, str) and m.strip()
            ]

            gender = char_info.get('gender', 'not_clear').strip().lower()
            if gender not in self.VALID_GENDERS:
                gender = 'not_clear'

            if not orig or not first_name:
                continue

            # Step 1: direct key match — update fields, but never erase known info
            if orig in self.characters:
                existing = self.characters[orig]
                existing['first_name'] = first_name
                if last_name or not existing.get('last_name'):
                    existing['last_name'] = last_name
                if middle_names or not existing.get('middle_names'):
                    existing['middle_names'] = middle_names
                if existing.get('gender', 'not_clear') == 'not_clear' and gender != 'not_clear':
                    existing['gender'] = gender
                updated += 1
                continue

            # Step 2: merge against an existing entry that's the same person
            # (same first_name, with exactly one side missing the surname)
            merge_target = self._find_character_merge_target(first_name, last_name)
            if merge_target is not None:
                target_orig, target_data = merge_target
                target_last = target_data.get('last_name', '')

                if last_name and not target_last:
                    # Incoming form is more complete — promote it to canonical
                    merged_gender = target_data.get('gender', 'not_clear')
                    if merged_gender == 'not_clear' and gender != 'not_clear':
                        merged_gender = gender

                    new_key = orig if len(orig) >= len(target_orig) else target_orig
                    merged_middle = middle_names or target_data.get('middle_names', [])

                    if new_key != target_orig:
                        del self.characters[target_orig]
                    self.characters[new_key] = {
                        'first_name': first_name,
                        'middle_names': merged_middle,
                        'last_name': last_name,
                        'gender': merged_gender,
                    }
                    logger.info(
                        f"Merged character: '{target_orig}' + incoming '{orig}' → '{new_key}' (last_name='{last_name}')"
                    )
                else:
                    # Existing entry is already the more complete one — only refine gender
                    if target_data.get('gender', 'not_clear') == 'not_clear' and gender != 'not_clear':
                        target_data['gender'] = gender
                    logger.info(
                        f"Skipped duplicate short-form '{orig}' for existing character '{target_orig}'"
                    )
                updated += 1
                continue

            # Step 3: genuinely new character
            self.characters[orig] = {
                'first_name': first_name,
                'middle_names': middle_names,
                'last_name': last_name,
                'gender': gender,
            }
            added += 1

        if added or updated:
            logger.info(f"Updated characters: {added} added, {updated} modified")
            self.save_characters()

    def _find_character_merge_target(
        self,
        first_name: str,
        last_name: str
    ) -> Optional[tuple]:
        """Find an existing entry that represents the same character.

        Match rule: same first_name (case-insensitive), with exactly one side
        having a surname set. This catches the common case where the LLM emits
        a short-form mention ("マサト") and a full-form mention ("マサト・イトウ")
        as two separate entries for the same person.
        """
        first_lower = first_name.lower()
        incoming_has_last = bool(last_name)

        for existing_orig, existing_data in self.characters.items():
            if existing_data.get('first_name', '').lower() != first_lower:
                continue
            existing_has_last = bool(existing_data.get('last_name', ''))
            if existing_has_last != incoming_has_last:
                return (existing_orig, existing_data)

        return None

    def update_places(self, places_data: List[Dict[str, str]]) -> None:
        """Update place list with new data.

        Args:
            places_data: List of place dictionaries with 'original' and 'translated'
        """
        if not self.context_mode or not places_data:
            return

        added = 0

        for place_info in places_data:
            if not isinstance(place_info, dict):
                continue

            if 'original' not in place_info or 'translated' not in place_info:
                continue

            orig = place_info['original'].strip()
            trans = place_info['translated'].strip()

            if orig and trans and orig not in self.places:
                self.places[orig] = trans
                added += 1

        if added:
            logger.info(f"Added {added} new places")
            self.save_places()

    def update_terms(self, terms_data: List[Dict[str, str]]) -> None:
        """Update specialized terms list with new data.

        Args:
            terms_data: List of term dictionaries with 'original', 'translated', 'category'
        """
        if not self.context_mode or not terms_data:
            return

        added = 0
        updated = 0

        for term_info in terms_data:
            if not isinstance(term_info, dict):
                continue

            if 'original' not in term_info or 'translated' not in term_info:
                continue

            orig = term_info['original'].strip()
            trans = term_info['translated'].strip()
            category = term_info.get('category', 'other').strip().lower()

            # Validate category
            if category not in self.VALID_TERM_CATEGORIES:
                category = 'other'

            if not orig or not trans:
                continue

            if orig not in self.terms:
                self.terms[orig] = {'translated': trans, 'category': category}
                added += 1
            else:
                self.terms[orig]['translated'] = trans
                # Only update category if current is 'other' and new is specific
                if self.terms[orig]['category'] == 'other' and category != 'other':
                    self.terms[orig]['category'] = category
                updated += 1

        if added or updated:
            logger.info(f"Updated terms: {added} added, {updated} modified")
            self.save_terms()

    def update_notes(
        self,
        notes_data: List[Dict[str, str]],
        update_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        """Update notes with ADD/UPDATE/DELETE operations.

        Args:
            notes_data: List of note dictionaries with 'action', 'key', 'note'
            update_callback: Optional callback for update notifications
        """
        if not self.notes_mode or not notes_data:
            return

        for note_info in notes_data:
            if not isinstance(note_info, dict):
                continue

            action = note_info.get('action', 'add').lower()
            key = note_info.get('key', '').strip()

            if not key:
                continue

            if action in ('add', 'update'):
                note = note_info.get('note', '').strip()
                if note:
                    old_note = self.notes.get(key, '')
                    self.notes[key] = note

                    if update_callback:
                        if old_note and old_note != note:
                            update_callback(f"Updated note '{key}': '{old_note}' → '{note}'")
                        elif not old_note:
                            update_callback(f"Added note '{key}': '{note}'")

            elif action in ('delete', 'remove'):
                if key in self.notes:
                    removed_note = self.notes[key]
                    del self.notes[key]
                    if update_callback:
                        update_callback(f"Removed note '{key}': '{removed_note}'")

        self.save_notes()

    def get_character_prompt(self) -> str:
        """Generate character context prompt for translation.

        Returns:
            Formatted string of character translations, or empty string
        """
        if not self.context_mode or not self.characters:
            return ""

        char_list = [
            f"{orig} : {format_character_name(data)} : {data.get('gender', 'not_clear')}"
            for orig, data in self.characters.items()
        ]
        char_string = "\n".join(char_list)
        return f"Existing Character Translations:\n{char_string}\n\n"

    def get_place_prompt(self) -> str:
        """Generate place context prompt for translation.

        Returns:
            Formatted string of place translations, or empty string
        """
        if not self.context_mode or not self.places:
            return ""

        place_list = "\n".join([f"{orig} : {trans}" for orig, trans in self.places.items()])
        return f"Existing Place Translations:\n{place_list}\n\n"

    def get_terms_prompt(self) -> str:
        """Generate specialized terms context prompt for translation.

        Returns:
            Formatted string of term translations, or empty string
        """
        if not self.context_mode or not self.terms:
            return ""

        terms_list = [
            f"{orig} : {data['translated']} : {data['category']}"
            for orig, data in self.terms.items()
        ]
        terms_string = "\n".join(terms_list)
        return f"Existing Specialized Term Translations:\n{terms_string}\n\n"

    def get_notes_prompt(self) -> str:
        """Generate translation notes prompt.

        Returns:
            Formatted string of translation notes, or empty string
        """
        if not self.notes_mode or not self.notes:
            return ""

        notes_list = "\n".join([f"{key} = {note}" for key, note in self.notes.items()])
        return f"Important Translation Notes:\n{notes_list}\n\n"

    def set_context_filter(
        self,
        context_filter: 'ContextFilter',
        enabled: bool = True,
        filter_characters: bool = False,
        filter_places: bool = True,
        filter_terms: bool = True
    ) -> None:
        self._context_filter = context_filter
        self._use_context_filter = enabled
        self._filter_characters = filter_characters
        self._filter_places = filter_places
        self._filter_terms = filter_terms

    def enable_context_filter(self, enabled: bool = True) -> None:
        self._use_context_filter = enabled and self._context_filter is not None

    @property
    def context_filter_enabled(self) -> bool:
        return self._use_context_filter and self._context_filter is not None

    def get_all_relevant_prompts(self, chunk_text: str) -> tuple:
        empty_details = {'characters': [], 'places': [], 'terms': []}

        if not self.context_mode:
            return ("", "", "", empty_details)

        if not self._use_context_filter or not self._context_filter:
            return (
                self.get_character_prompt(),
                self.get_place_prompt(),
                self.get_terms_prompt(),
                empty_details
            )

        match_details = {'characters': [], 'places': [], 'terms': []}

        if self._filter_characters:
            relevant_chars, match_details['characters'] = self._context_filter.filter_characters(
                chunk_text, self.characters
            )
        else:
            relevant_chars = self.characters

        if self._filter_places:
            relevant_places, match_details['places'] = self._context_filter.filter_places(
                chunk_text, self.places
            )
        else:
            relevant_places = self.places

        if self._filter_terms:
            relevant_terms, match_details['terms'] = self._context_filter.filter_terms(
                chunk_text, self.terms
            )
        else:
            relevant_terms = self.terms

        char_prompt = ""
        if relevant_chars:
            char_list = [
                f"{orig} : {format_character_name(data)} : {data.get('gender', 'not_clear')}"
                for orig, data in relevant_chars.items()
            ]
            char_prompt = f"Existing Character Translations:\n" + "\n".join(char_list) + "\n\n"

        place_prompt = ""
        if relevant_places:
            place_list = "\n".join([f"{orig} : {trans}" for orig, trans in relevant_places.items()])
            place_prompt = f"Existing Place Translations:\n{place_list}\n\n"

        terms_prompt = ""
        if relevant_terms:
            terms_list = [
                f"{orig} : {data['translated']} : {data['category']}"
                for orig, data in relevant_terms.items()
            ]
            terms_prompt = f"Existing Specialized Term Translations:\n" + "\n".join(terms_list) + "\n\n"

        return (char_prompt, place_prompt, terms_prompt, match_details)
