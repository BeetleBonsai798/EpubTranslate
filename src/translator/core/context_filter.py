"""Context filter for finding terms that actually appear in text chunks."""

import logging
import math
from collections import OrderedDict
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class ContextFilter:
    """Filters context to only include terms that appear in the text chunk.

    Uses multiple matching strategies to handle language variations:
    - Direct substring match
    - Normalized matching (hiragana/katakana conversion for Japanese)
    - Partial matching for compound names
    """

    HIRAGANA_START = 0x3041
    HIRAGANA_END = 0x3096
    KATAKANA_START = 0x30A1
    KATAKANA_END = 0x30F6

    def __init__(self):
        pass

    def _katakana_to_hiragana(self, text: str) -> str:
        result = []
        for char in text:
            code = ord(char)
            if self.KATAKANA_START <= code <= self.KATAKANA_END:
                result.append(chr(code - self.KATAKANA_START + self.HIRAGANA_START))
            else:
                result.append(char)
        return ''.join(result)

    def _normalize_japanese(self, text: str) -> str:
        return self._katakana_to_hiragana(text.lower())

    def _is_cjk_char(self, char: str) -> bool:
        code = ord(char)
        return (
            (0x4E00 <= code <= 0x9FFF) or
            (0x3400 <= code <= 0x4DBF) or
            (0x3040 <= code <= 0x309F) or
            (0x30A0 <= code <= 0x30FF) or
            (0xAC00 <= code <= 0xD7AF)
        )

    def _has_cjk(self, text: str) -> bool:
        return any(self._is_cjk_char(c) for c in text)

    def _find_match_in_chunk(
        self,
        term: str,
        chunk: str,
        chunk_normalized: str,
        allow_loose_partial: bool = False,
        prefix_only: bool = False
    ) -> Optional[Tuple[str, str]]:
        if term in chunk:
            return (term, "exact")

        term_normalized = self._normalize_japanese(term)
        if term_normalized in chunk_normalized:
            return (term, "normalized")

        if self._has_cjk(term) and len(term) >= 2:
            min_partial_len = max(2, math.ceil(len(term) * 0.7))

            for length in range(len(term) - 1, min_partial_len - 1, -1):
                for start in range(len(term) - length + 1):
                    partial = term[start:start + length]
                    if partial in chunk:
                        return (partial, "partial")
                    partial_norm = self._normalize_japanese(partial)
                    if partial_norm in chunk_normalized:
                        return (partial, "partial_norm")

            if (allow_loose_partial or prefix_only) and len(term) >= 4:
                half_len = len(term) // 2
                first_half = term[:half_len]

                if len(first_half) >= 2 and first_half in chunk:
                    return (first_half, "prefix" if prefix_only else "name_part")

                first_half_norm = self._normalize_japanese(first_half)
                min_norm_len = 3 if prefix_only else 2
                if len(first_half) >= min_norm_len and first_half_norm in chunk_normalized:
                    return (first_half, "prefix_norm" if prefix_only else "name_part_norm")

                if allow_loose_partial and not prefix_only:
                    second_half = term[half_len:]
                    if len(second_half) >= 2 and second_half in chunk:
                        return (second_half, "name_part")

                    second_half_norm = self._normalize_japanese(second_half)
                    if len(second_half) >= 2 and second_half_norm in chunk_normalized:
                        return (second_half, "name_part_norm")

        return None

    def filter_characters(
        self,
        chunk: str,
        characters: OrderedDict[str, Dict[str, str]]
    ) -> Tuple[OrderedDict[str, Dict[str, str]], List[Tuple[str, str, str, str]]]:
        if not characters:
            return OrderedDict(), []

        chunk_normalized = self._normalize_japanese(chunk)
        relevant = OrderedDict()
        match_details = []

        for orig, char_data in characters.items():
            match = self._find_match_in_chunk(orig, chunk, chunk_normalized, allow_loose_partial=True)

            if match is None and isinstance(char_data, dict):
                translated = char_data.get('translated', '')
                if translated:
                    match = self._find_match_in_chunk(translated, chunk, chunk_normalized, allow_loose_partial=True)

            if match:
                relevant[orig] = char_data
                matched_text, match_type = match
                translated = char_data.get('translated', '') if isinstance(char_data, dict) else str(char_data)
                match_details.append((orig, translated, matched_text, match_type))

        logger.debug(f"Character filter: {len(relevant)}/{len(characters)} matched")
        return relevant, match_details

    def filter_places(
        self,
        chunk: str,
        places: OrderedDict[str, str]
    ) -> Tuple[OrderedDict[str, str], List[Tuple[str, str, str, str]]]:
        if not places:
            return OrderedDict(), []

        chunk_normalized = self._normalize_japanese(chunk)
        relevant = OrderedDict()
        match_details = []

        for orig, trans in places.items():
            match = self._find_match_in_chunk(orig, chunk, chunk_normalized)

            if match is None and trans:
                match = self._find_match_in_chunk(trans, chunk, chunk_normalized)

            if match:
                relevant[orig] = trans
                matched_text, match_type = match
                match_details.append((orig, trans, matched_text, match_type))

        logger.debug(f"Place filter: {len(relevant)}/{len(places)} matched")
        return relevant, match_details

    def filter_terms(
        self,
        chunk: str,
        terms: OrderedDict[str, Dict[str, str]]
    ) -> Tuple[OrderedDict[str, Dict[str, str]], List[Tuple[str, str, str, str]]]:
        if not terms:
            return OrderedDict(), []

        chunk_normalized = self._normalize_japanese(chunk)
        relevant = OrderedDict()
        match_details = []

        for orig, term_data in terms.items():
            match = self._find_match_in_chunk(orig, chunk, chunk_normalized, prefix_only=True)

            if match is None and isinstance(term_data, dict):
                translated = term_data.get('translated', '')
                if translated:
                    match = self._find_match_in_chunk(translated, chunk, chunk_normalized, prefix_only=True)

            if match:
                relevant[orig] = term_data
                matched_text, match_type = match
                translated = term_data.get('translated', '') if isinstance(term_data, dict) else str(term_data)
                match_details.append((orig, translated, matched_text, match_type))

        logger.debug(f"Term filter: {len(relevant)}/{len(terms)} matched")
        return relevant, match_details

    def filter_all(
        self,
        chunk: str,
        characters: OrderedDict[str, Dict[str, str]],
        places: OrderedDict[str, str],
        terms: OrderedDict[str, Dict[str, str]]
    ) -> Tuple[
        OrderedDict[str, Dict[str, str]],
        OrderedDict[str, str],
        OrderedDict[str, Dict[str, str]],
        Dict[str, List[Tuple[str, str, str, str]]]
    ]:
        rel_chars, char_details = self.filter_characters(chunk, characters)
        rel_places, place_details = self.filter_places(chunk, places)
        rel_terms, term_details = self.filter_terms(chunk, terms)

        details = {
            'characters': char_details,
            'places': place_details,
            'terms': term_details
        }

        logger.info(
            f"Context filter: {len(rel_chars)}/{len(characters)} chars, "
            f"{len(rel_places)}/{len(places)} places, "
            f"{len(rel_terms)}/{len(terms)} terms"
        )

        return rel_chars, rel_places, rel_terms, details
