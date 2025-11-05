"""Context management for characters, places, terms, and translation notes."""

import json
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger(__name__)


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

            char_dict = OrderedDict()
            for orig, char_data in data.items():
                if isinstance(char_data, dict):
                    char_dict[orig] = char_data
                else:
                    # Legacy format support
                    char_dict[orig] = {'translated': char_data, 'gender': 'not_clear'}

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

            terms_dict = OrderedDict()
            for orig, term_data in data.items():
                if isinstance(term_data, dict):
                    terms_dict[orig] = term_data
                else:
                    # Legacy format support
                    terms_dict[orig] = {'translated': term_data, 'category': 'other'}

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

    def update_characters(self, characters_data: List[Dict[str, str]]) -> None:
        """Update character list with new data.

        Args:
            characters_data: List of character dictionaries with 'original', 'translated', 'gender'
        """
        if not self.context_mode or not characters_data:
            return

        added = 0
        updated = 0

        for char_info in characters_data:
            if not isinstance(char_info, dict):
                continue

            if 'original' not in char_info or 'translated' not in char_info:
                continue

            orig = char_info['original'].strip()
            trans = char_info['translated'].strip()
            gender = char_info.get('gender', 'not_clear').strip().lower()

            # Validate gender
            if gender not in self.VALID_GENDERS:
                gender = 'not_clear'

            if not orig or not trans:
                continue

            if orig not in self.characters:
                self.characters[orig] = {'translated': trans, 'gender': gender}
                added += 1
            else:
                self.characters[orig]['translated'] = trans
                # Only update gender if current is unclear and new is clear
                if self.characters[orig]['gender'] == 'not_clear' and gender != 'not_clear':
                    self.characters[orig]['gender'] = gender
                updated += 1

        if added or updated:
            logger.info(f"Updated characters: {added} added, {updated} modified")
            self.save_characters()

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

        char_list = []
        for orig, char_data in self.characters.items():
            if isinstance(char_data, dict):
                trans = char_data['translated']
                gender = char_data['gender']
                char_list.append(f"{orig} : {trans} : {gender}")
            else:
                # Legacy format support
                char_list.append(f"{orig} : {char_data} : not_clear")

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

        terms_list = []
        for orig, term_data in self.terms.items():
            if isinstance(term_data, dict):
                trans = term_data['translated']
                category = term_data['category']
                terms_list.append(f"{orig} : {trans} : {category}")
            else:
                # Legacy format support
                terms_list.append(f"{orig} : {term_data} : other")

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
