"""Provider definitions for supported LLM API endpoints.

Each provider declares its configuration (env vars, config keys, defaults)
and capabilities (model fetching, reasoning, JSON schema, provider routing).
Provider-specific request building (extra headers, extra body, reasoning params)
is encapsulated in prepare_request().
"""


class BaseProvider:
    key = ""
    display_name = ""
    default_base_url = ""

    api_key_env_var = ""
    endpoint_url_env_var = None

    api_key_config_key = ""
    model_config_key = ""
    url_config_key = None

    can_fetch_models = False
    can_fetch_providers = False
    has_reasoning = False
    has_json_schema = False
    has_configurable_url = False

    default_models = []
    default_model = ""

    def prepare_request(self, request_params, reasoning_config,
                        json_output_mode, json_schema=None,
                        current_provider=None, top_k=0):
        """Apply provider-specific settings to the API request.

        Modifies request_params in-place. Returns (extra_body, extra_headers).
        """
        extra_body = {}
        extra_headers = {}

        if top_k > 0:
            extra_body['top_k'] = top_k

        if json_output_mode == 'json_object':
            request_params['response_format'] = {'type': 'json_object'}
        elif json_output_mode == 'json_schema':
            request_params['response_format'] = {'type': 'json_object'}

        return extra_body, extra_headers

    def get_provider_list(self, configured_providers):
        return [None]

    def get_model_from_endpoint_config(self, endpoint_config):
        return endpoint_config.get('model', '')


class OpenRouterProvider(BaseProvider):
    key = "openrouter"
    display_name = "OpenRouter"
    default_base_url = "https://openrouter.ai/api/v1"
    models_url = "https://openrouter.ai/api/v1/models"

    api_key_env_var = "OPENROUTER_API_KEY"
    api_key_config_key = "api_key"
    model_config_key = "model"

    can_fetch_models = True
    can_fetch_providers = True
    has_reasoning = True
    has_json_schema = True

    default_model = "deepseek/deepseek-v3.2-exp"
    default_provider_order = [
        'novita/fp8', 'siliconflow/fp8', 'deepinfra/fp4', 'gmicloud/fp8'
    ]

    def prepare_request(self, request_params, reasoning_config,
                        json_output_mode, json_schema=None,
                        current_provider=None, top_k=0):
        extra_body, extra_headers = super().prepare_request(
            request_params, reasoning_config, json_output_mode,
            json_schema, current_provider, top_k,
        )

        extra_headers.update({
            "HTTP-Referer": "https://github.com/BeetleBonsai798/EpubTranslate",
            "X-Title": "EpubTranslate",
        })

        if current_provider:
            extra_body['provider'] = {
                'order': [current_provider],
                'allow_fallbacks': False,
            }

        if reasoning_config.get('enabled'):
            r = {}
            if reasoning_config.get('max_tokens', 0) > 0:
                r['max_tokens'] = reasoning_config['max_tokens']
            else:
                r['effort'] = reasoning_config.get('effort', 'medium')
            if reasoning_config.get('exclude'):
                r['exclude'] = True
            extra_body['reasoning'] = r

        if json_output_mode == 'json_schema' and json_schema:
            request_params['response_format'] = {
                'type': 'json_schema',
                'json_schema': json_schema,
            }

        return extra_body, extra_headers

    def get_provider_list(self, configured_providers):
        if configured_providers:
            return configured_providers
        return list(self.default_provider_order)


class DeepSeekProvider(BaseProvider):
    key = "deepseek"
    display_name = "DeepSeek"
    default_base_url = "https://api.deepseek.com"

    api_key_env_var = "DEEPSEEK_API_KEY"
    endpoint_url_env_var = "DEEPSEEK_ENDPOINT_URL"
    api_key_config_key = "deepseek_api_key"
    model_config_key = "deepseek_model"
    url_config_key = "deepseek_endpoint_url"

    can_fetch_models = True
    has_reasoning = True
    has_configurable_url = True

    default_models = [
        "deepseek-v4-flash", "deepseek-v4-pro",
        "deepseek-chat", "deepseek-reasoner",
    ]
    default_model = "deepseek-v4-pro"

    def prepare_request(self, request_params, reasoning_config,
                        json_output_mode, json_schema=None,
                        current_provider=None, top_k=0):
        extra_body, extra_headers = super().prepare_request(
            request_params, reasoning_config, json_output_mode,
            json_schema, current_provider, top_k,
        )

        if reasoning_config.get('enabled'):
            extra_body['thinking'] = {'type': 'enabled'}
            request_params['reasoning_effort'] = reasoning_config.get('effort', 'high')
        else:
            extra_body['thinking'] = {'type': 'disabled'}

        return extra_body, extra_headers


class MimoProvider(BaseProvider):
    key = "mimo"
    display_name = "Mimo"
    default_base_url = "https://api.xiaomimimo.com/v1"

    api_key_env_var = "MIMO_API_KEY"
    endpoint_url_env_var = "MIMO_ENDPOINT_URL"
    api_key_config_key = "mimo_api_key"
    model_config_key = "mimo_model"
    url_config_key = "mimo_endpoint_url"

    can_fetch_models = False
    has_reasoning = True
    has_configurable_url = True

    default_models = ["mimo-v2.5-pro", "mimo-v2.5", "mimo-v2-flash"]
    default_model = "mimo-v2.5-pro"

    def prepare_request(self, request_params, reasoning_config,
                        json_output_mode, json_schema=None,
                        current_provider=None, top_k=0):
        extra_body, extra_headers = super().prepare_request(
            request_params, reasoning_config, json_output_mode,
            json_schema, current_provider, top_k,
        )

        if reasoning_config.get('enabled'):
            extra_body['thinking'] = {'type': 'enabled'}
        else:
            extra_body['thinking'] = {'type': 'disabled'}

        return extra_body, extra_headers


class CustomProvider(BaseProvider):
    key = "custom"
    display_name = "Custom Endpoint"
    default_base_url = ""

    api_key_env_var = "CUSTOM_ENDPOINT_KEY"
    endpoint_url_env_var = "CUSTOM_ENDPOINT_URL"
    api_key_config_key = "custom_endpoint_key"
    model_config_key = "custom_endpoint_model"
    url_config_key = "custom_endpoint_url"

    has_configurable_url = True


PROVIDERS = {
    'openrouter': OpenRouterProvider(),
    'deepseek': DeepSeekProvider(),
    'mimo': MimoProvider(),
    'custom': CustomProvider(),
}
