"""Configuration management for the translator."""

from .config_manager import (
    ConfigManager,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODELS_URL,
    DEFAULT_PROVIDERS,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_DEFAULT_MODELS,
)

__all__ = [
    'ConfigManager',
    'OPENROUTER_BASE_URL',
    'OPENROUTER_MODELS_URL',
    'DEFAULT_PROVIDERS',
    'DEEPSEEK_BASE_URL',
    'DEEPSEEK_DEFAULT_MODELS',
]
