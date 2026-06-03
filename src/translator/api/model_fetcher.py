"""Generic model fetcher for OpenAI-compatible /models endpoints (DeepSeek, Mimo, etc.)."""

import json
import logging
import requests
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class ModelFetcher(QThread):
    """Thread to fetch model lists from OpenAI-compatible /models endpoints."""

    models_fetched = Signal(list)
    error_occurred = Signal(str)
    progress_updated = Signal(str)

    def __init__(self, base_url, api_key="", provider_name="API"):
        super().__init__()
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.provider_name = provider_name

    def run(self):
        try:
            self.fetch_models()
        except Exception as e:
            self.error_occurred.emit(f"Error fetching models from {self.provider_name}: {str(e)}")

    def fetch_models(self):
        url = f"{self.base_url}/models"
        self.progress_updated.emit(f"Fetching models from {self.provider_name}...")

        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            if 'data' in data:
                models = [
                    entry.get('id', '')
                    for entry in data['data']
                    if entry.get('id')
                ]
                models.sort()
                self.models_fetched.emit(models)
                self.progress_updated.emit(
                    f"Fetched {len(models)} models from {self.provider_name}"
                )
            else:
                self.error_occurred.emit(
                    f"Unexpected response format from {self.provider_name}"
                )

        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"JSON decode error: {str(e)}")
