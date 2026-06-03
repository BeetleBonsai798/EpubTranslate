"""Configuration manager for application settings and environment variables."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from ..providers import PROVIDERS

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration, separating secrets from settings.

    API keys are loaded from .env file for security.
    Other settings are loaded from translator_config.json for easy editing.
    """

    def __init__(self):
        project_root = Path(__file__).parent.parent.parent.parent
        self.config_file = project_root / "translator_config.json"
        self.last_session_file = project_root / "last_session.json"
        self.env_file = project_root / ".env"

        openrouter = PROVIDERS['openrouter']

        self.default_config = {
            "chunk_tokens": 7000,
            "temperature": 0.9,
            "max_tokens": 12000,
            "frequency_penalty": 0.0,
            "top_p": 0.95,
            "top_k": 0,
            "timeout": 10.0,
            "selected_providers": list(openrouter.default_provider_order),
            "retries_per_provider": 2,
            "context_mode": True,
            "notes_mode": False,
            "power_steering": False,
            "send_previous": False,
            "previous_chapters": 1,
            "send_previous_chunks": False,
            "concurrent_workers": 1,
            "chapter_selection_mode": "range",
            "start_chapter": "1",
            "end_chapter": "1",
            "csv_chapters": "",
            "last_epub_path": "",
            "endpoint_type": "openrouter",
            "reasoning_enabled": False,
            "reasoning_effort": "medium",
            "reasoning_max_tokens": 0,
            "reasoning_exclude": False,
            "json_output_mode": "off",
            "window_geometry": {
                "x": 100,
                "y": 100,
                "width": 1200,
                "height": 800
            },
            "compress_paragraphs": False,
            "context_filter_enabled": False,
            "context_filter_characters": False,
            "context_filter_places": True,
            "context_filter_terms": True,
            "base_prompt_position": "bottom",
        }

        for provider in PROVIDERS.values():
            if provider.model_config_key and provider.default_model:
                self.default_config[provider.model_config_key] = provider.default_model

        self._env_vars: Dict[str, str] = {}
        self._load_env_file()

    def _load_env_file(self) -> None:
        if self.env_file.exists():
            try:
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' in line:
                            key, value = line.split('=', 1)
                            self._env_vars[key.strip()] = value.strip()
                logger.info("Loaded environment variables from .env file")
            except Exception as e:
                logger.error(f"Error loading .env file: {e}", exc_info=True)
        else:
            logger.warning(
                f".env file not found at {self.env_file}. "
                "Copy .env.example to .env and add your API keys."
            )

    def get_api_key(self, key_name: str) -> str:
        return self._env_vars.get(key_name) or os.environ.get(key_name, "")

    def save_env_var(self, key_name: str, value: str) -> bool:
        try:
            lines = []
            found = False
            if self.env_file.exists():
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped and not stripped.startswith('#') and '=' in stripped:
                            existing_key = stripped.split('=', 1)[0].strip()
                            if existing_key == key_name:
                                lines.append(f"{key_name}={value}\n")
                                found = True
                                continue
                        lines.append(line)

            if not found:
                if lines and not lines[-1].endswith('\n'):
                    lines[-1] = lines[-1] + '\n'
                lines.append(f"{key_name}={value}\n")

            with open(self.env_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            self._env_vars[key_name] = value
            return True

        except Exception as e:
            logger.error(f"Error saving env var {key_name}: {e}", exc_info=True)
            return False

    def _inject_provider_env(self, config: Dict[str, Any],
                             file_config: Optional[Dict[str, Any]] = None) -> None:
        """Inject API keys and endpoint URLs from environment into config."""
        for provider in PROVIDERS.values():
            if provider.api_key_env_var:
                config[provider.api_key_config_key] = self.get_api_key(
                    provider.api_key_env_var
                )
            if provider.endpoint_url_env_var and provider.url_config_key:
                config[provider.url_config_key] = (
                    self._env_vars.get(provider.endpoint_url_env_var)
                    or (file_config or {}).get(
                        provider.url_config_key, provider.default_base_url
                    )
                    or provider.default_base_url
                )

    def load_config(self) -> Dict[str, Any]:
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                merged_config = self.default_config.copy()
                merged_config.update(config)
                self._inject_provider_env(merged_config, file_config=config)

                logger.info(f"Loaded configuration from {self.config_file}")
                return merged_config
            else:
                logger.warning(
                    f"Config file not found at {self.config_file}. "
                    "Using default configuration."
                )
                default = self.default_config.copy()
                self._inject_provider_env(default)
                return default

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}", exc_info=True)
            return self._get_default_with_env()
        except Exception as e:
            logger.error(f"Error loading config: {e}", exc_info=True)
            return self._get_default_with_env()

    def _get_default_with_env(self) -> Dict[str, Any]:
        default = self.default_config.copy()
        self._inject_provider_env(default)
        return default

    def save_config(self, config: Dict[str, Any]) -> bool:
        try:
            for provider in PROVIDERS.values():
                if provider.api_key_env_var:
                    val = config.get(provider.api_key_config_key, '')
                    if val:
                        self.save_env_var(provider.api_key_env_var, val)
                if provider.endpoint_url_env_var and provider.url_config_key:
                    val = config.get(provider.url_config_key, '')
                    if val:
                        self.save_env_var(provider.endpoint_url_env_var, val)

            config_to_save = config.copy()
            for provider in PROVIDERS.values():
                if provider.api_key_config_key:
                    config_to_save.pop(provider.api_key_config_key, None)

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved configuration to {self.config_file}")
            return True

        except IOError as e:
            logger.error(f"IO error saving config: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Error saving config: {e}", exc_info=True)
            return False

    def save_last_session(self, session_data: Dict[str, Any]) -> bool:
        try:
            with open(self.last_session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved session data to {self.last_session_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving last session: {e}", exc_info=True)
            return False

    def load_last_session(self) -> Optional[Dict[str, Any]]:
        try:
            if self.last_session_file.exists():
                with open(self.last_session_file, 'r', encoding='utf-8') as f:
                    session = json.load(f)
                logger.debug(f"Loaded session data from {self.last_session_file}")
                return session
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in session file: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Error loading last session: {e}", exc_info=True)
            return None
