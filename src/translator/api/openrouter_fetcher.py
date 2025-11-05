"""OpenRouter API fetcher for models and providers."""

import json
import requests
import urllib.parse
from PyQt5.QtCore import QThread, pyqtSignal


class OpenRouterFetcher(QThread):
    """Thread to fetch models and providers from OpenRouter API."""

    models_fetched = pyqtSignal(list)
    providers_fetched = pyqtSignal(str, list)
    provider_details_fetched = pyqtSignal(str, list)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(str)

    def __init__(self, fetch_type="models", model_id=None):
        super().__init__()
        self.fetch_type = fetch_type
        self.model_id = model_id

    def run(self):
        try:
            if self.fetch_type == "models":
                self.fetch_models()
            elif self.fetch_type == "providers":
                self.fetch_providers()
        except Exception as e:
            self.error_occurred.emit(f"Error fetching {self.fetch_type}: {str(e)}")

    def fetch_models(self):
        """Fetch available models from OpenRouter."""
        self.progress_updated.emit("Fetching models from OpenRouter...")
        try:
            response = requests.get("https://openrouter.ai/api/v1/models", timeout=30)
            response.raise_for_status()
            data = response.json()

            if 'data' in data:
                models = []
                for model in data['data']:
                    model_info = {
                        'id': model.get('id', ''),
                        'name': model.get('name', ''),
                        'description': model.get('description', ''),
                        'context_length': model.get('context_length', 0),
                        'pricing': model.get('pricing', {}),
                        'top_provider': model.get('top_provider', {})
                    }
                    models.append(model_info)

                self.models_fetched.emit(models)
                self.progress_updated.emit(f"Successfully fetched {len(models)} models")
            else:
                self.error_occurred.emit("Invalid response format from OpenRouter")

        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"JSON decode error: {str(e)}")

    def fetch_providers(self):
        """Fetch providers for a specific model."""
        if not self.model_id:
            self.error_occurred.emit("No model ID provided for provider fetch")
            return

        self.progress_updated.emit(f"Fetching providers for {self.model_id}...")
        try:
            clean_model_id = self.model_id.split(' ')[0].split('(')[0].strip()

            if '/' in clean_model_id:
                author, slug = clean_model_id.split('/', 1)

                author_encoded = urllib.parse.quote(author, safe='')
                slug_encoded = urllib.parse.quote(slug, safe='')

                url = f"https://openrouter.ai/api/v1/models/{author_encoded}/{slug_encoded}/endpoints"
                print(f"Requesting URL: {url}")
                self.progress_updated.emit(f"Requesting: {url}")

                response = requests.get(url, timeout=30)
                print(f"Response status: {response.status_code}")
                response.raise_for_status()

                data = response.json()
                providers = []
                provider_details = []

                if isinstance(data, dict) and 'data' in data:
                    model_data = data['data']
                    if 'endpoints' in model_data and isinstance(model_data['endpoints'], list):
                        print(f"Found {len(model_data['endpoints'])} endpoints")

                        for i, endpoint in enumerate(model_data['endpoints']):
                            print(f"Processing endpoint {i}: {endpoint.get('provider_name', 'Unknown')}")

                            if isinstance(endpoint, dict) and 'provider_name' in endpoint:
                                provider_name = endpoint['provider_name']

                                if 'tag' in endpoint and endpoint['tag']:
                                    provider_id = endpoint['tag']
                                else:
                                    provider_id = provider_name.lower()
                                    if 'quantization' in endpoint and endpoint['quantization']:
                                        provider_id += f"/{endpoint['quantization'].lower()}"

                                pricing_info = ""
                                if 'pricing' in endpoint and isinstance(endpoint['pricing'], dict):
                                    pricing = endpoint['pricing']
                                    prompt_price = float(pricing.get('prompt', 0))
                                    completion_price = float(pricing.get('completion', 0))

                                    prompt_per_1m = prompt_price * 1_000_000
                                    completion_per_1m = completion_price * 1_000_000
                                    pricing_info = f"${prompt_per_1m:.3f}/${completion_per_1m:.3f} per 1M tokens"

                                context_length = endpoint.get('context_length', 'Unknown')
                                quantization = endpoint.get('quantization', 'full precision')
                                if not quantization:
                                    quantization = 'full precision'

                                uptime = endpoint.get('uptime_last_30m')
                                uptime_str = f"{uptime:.1f}%" if uptime is not None else "N/A"

                                providers.append(provider_id)

                                detail_info = {
                                    'provider_id': provider_id,
                                    'provider_name': provider_name,
                                    'pricing': pricing_info,
                                    'context_length': context_length,
                                    'quantization': quantization,
                                    'uptime': uptime_str
                                }
                                provider_details.append(detail_info)
                                print(f"Added provider: {provider_id} - {pricing_info}")
                            else:
                                print(f"Invalid endpoint structure: {endpoint}")
                    else:
                        print(f"No 'endpoints' field found in model data. Available keys: {list(model_data.keys())}")
                else:
                    print(f"Invalid response structure. Expected dict with 'data' key, got: {type(data)}")
                    if isinstance(data, dict):
                        print(f"Available keys: {list(data.keys())}")

                print(f"Final providers list: {providers}")

                if providers:
                    self.providers_fetched.emit(clean_model_id, providers)
                    self.provider_details_fetched.emit(clean_model_id, provider_details)
                    self.progress_updated.emit(f"Found {len(providers)} providers for {clean_model_id}")
                else:
                    self.error_occurred.emit(f"No providers found for {clean_model_id}")
            else:
                self.error_occurred.emit(f"Invalid model ID format: {clean_model_id}")

        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"Network error fetching providers: {str(e)}")
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"JSON decode error: {str(e)}")
        except Exception as e:
            self.error_occurred.emit(f"Unexpected error: {str(e)}")
