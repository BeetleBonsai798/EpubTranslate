"""Configuration manager for application settings and environment variables."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration, separating secrets from settings.

    API keys are loaded from .env file for security.
    Other settings are loaded from translator_config.json for easy editing.
    """

    def __init__(self):
        """Initialize configuration manager with default paths and values."""
        project_root = Path(__file__).parent.parent.parent.parent
        self.config_file = project_root / "translator_config.json"
        self.last_session_file = project_root / "last_session.json"
        self.env_file = project_root / ".env"

        self.default_config = {
            "model": "deepseek/deepseek-v3.2-exp",
            "chunk_tokens": 7000,
            "temperature": 0.9,
            "max_tokens": 12000,
            "frequency_penalty": 0.0,
            "top_p": 0.95,
            "top_k": 0,
            "timeout": 10.0,
            "selected_providers": [
                "novita/fp8",
                "siliconflow/fp8",
                "deepinfra/fp4",
                "gmicloud/fp8"
            ],
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
            "use_custom_endpoint": False,
            "custom_endpoint_model": "deepseek-ai/DeepSeek-V3.2-Exp",
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
            "base_prompt_position": "bottom"
        }

        self._env_vars: Dict[str, str] = {}
        self._load_env_file()

    def _load_env_file(self) -> None:
        """Load environment variables from .env file.

        Reads key=value pairs from .env file and stores them.
        Falls back to system environment variables if .env doesn't exist.
        """
        if self.env_file.exists():
            try:
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if not line or line.startswith('#'):
                            continue
                        # Parse key=value pairs
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
        """Get API key from environment variables.

        Args:
            key_name: Name of the environment variable (e.g., 'OPENROUTER_API_KEY')

        Returns:
            API key value or empty string if not found
        """
        # Check loaded .env vars first, then fall back to system env vars
        return self._env_vars.get(key_name) or os.environ.get(key_name, "")

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file with environment variable injection.

        Returns:
            Configuration dictionary with API keys from environment
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # Merge with default config to handle new settings
                merged_config = self.default_config.copy()
                merged_config.update(config)

                # Inject API keys from environment
                merged_config['api_key'] = self.get_api_key('OPENROUTER_API_KEY')
                merged_config['custom_endpoint_url'] = (
                    self._env_vars.get('CUSTOM_ENDPOINT_URL') or
                    config.get('custom_endpoint_url', 'https://llm.chutes.ai/v1')
                )
                merged_config['custom_endpoint_key'] = self.get_api_key('CUSTOM_ENDPOINT_KEY')

                logger.info(f"Loaded configuration from {self.config_file}")
                return merged_config
            else:
                logger.warning(
                    f"Config file not found at {self.config_file}. "
                    "Using default configuration."
                )
                default = self.default_config.copy()
                default['api_key'] = self.get_api_key('OPENROUTER_API_KEY')
                default['custom_endpoint_url'] = self._env_vars.get(
                    'CUSTOM_ENDPOINT_URL',
                    'https://llm.chutes.ai/v1'
                )
                default['custom_endpoint_key'] = self.get_api_key('CUSTOM_ENDPOINT_KEY')
                return default

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}", exc_info=True)
            return self._get_default_with_env()
        except Exception as e:
            logger.error(f"Error loading config: {e}", exc_info=True)
            return self._get_default_with_env()

    def _get_default_with_env(self) -> Dict[str, Any]:
        """Get default config with environment variables injected."""
        default = self.default_config.copy()
        default['api_key'] = self.get_api_key('OPENROUTER_API_KEY')
        default['custom_endpoint_url'] = self._env_vars.get(
            'CUSTOM_ENDPOINT_URL',
            'https://llm.chutes.ai/v1'
        )
        default['custom_endpoint_key'] = self.get_api_key('CUSTOM_ENDPOINT_KEY')
        return default

    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file without saving API keys.

        Args:
            config: Configuration dictionary to save

        Returns:
            True if save successful, False otherwise
        """
        try:
            # Create a copy and remove sensitive keys
            config_to_save = config.copy()
            config_to_save.pop('api_key', None)
            config_to_save.pop('custom_endpoint_key', None)
            # Keep custom_endpoint_url as it's not sensitive

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
        """Save last session data for continuation.

        Args:
            session_data: Session data dictionary

        Returns:
            True if save successful, False otherwise
        """
        try:
            with open(self.last_session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved session data to {self.last_session_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving last session: {e}", exc_info=True)
            return False

    def load_last_session(self) -> Optional[Dict[str, Any]]:
        """Load last session data.

        Returns:
            Session data dictionary or None if not found
        """
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
