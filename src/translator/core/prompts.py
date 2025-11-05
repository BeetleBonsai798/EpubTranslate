"""System prompts for translation."""

import json
import os
from pathlib import Path

def _load_prompts_config():
    config_path = Path(__file__).parent.parent.parent.parent / "prompts_config.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"prompts_config.json not found at {config_path}. "
            "Please ensure the configuration file exists in the project root."
        )

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

_PROMPTS_CONFIG = _load_prompts_config()

SYSTEM_PROMPT = _PROMPTS_CONFIG["system_prompt"]
TOC_SYSTEM_PROMPT = _PROMPTS_CONFIG["toc_system_prompt"]
CHARACTER_INSTRUCTION = _PROMPTS_CONFIG["character_instruction"]
PLACES_INSTRUCTION = _PROMPTS_CONFIG["places_instruction"]
TERMS_INSTRUCTION = _PROMPTS_CONFIG["terms_instruction"]
NOTES_DETAILED_INSTRUCTION = _PROMPTS_CONFIG["notes_detailed_instruction"]
NOTES_MANAGEMENT_INSTRUCTION = _PROMPTS_CONFIG["notes_management_instruction"]
NOTES_REMINDER = _PROMPTS_CONFIG["notes_reminder"]
BASE_INSTRUCTION = _PROMPTS_CONFIG["base_instruction"]
ENDING_INSTRUCTION = _PROMPTS_CONFIG["ending_instruction"]
COMPLETE_TRANSLATION_INSTRUCTION = _PROMPTS_CONFIG["complete_translation_instruction"]
