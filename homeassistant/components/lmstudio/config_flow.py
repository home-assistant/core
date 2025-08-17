"""Config flow for LM Studio integration."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import openai
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_BASE_URL,
    CONF_MAX_TOKENS,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_API_KEY,
    DEFAULT_BASE_URL,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_P,
    DOMAIN,
    MAX_MAX_TOKENS,
    MAX_TEMPERATURE,
    MAX_TOP_P,
    MIN_MAX_TOKENS,
    MIN_TEMPERATURE,
    MIN_TOP_P,
    TEMPERATURE_STEP,
    TOP_P_STEP,
)

_LOGGER = logging.getLogger(__name__)


async def _fetch_available_models(
    hass: HomeAssistant, base_url: str, api_key: str
) -> list[SelectOptionDict]:
    """Fetch available models from LM Studio server.

    Args:
        hass: HomeAssistant instance
        base_url: LM Studio server base URL
        api_key: API key for authentication

    Returns:
        List of SelectOptionDict with available models

    Raises:
        Exception: If unable to fetch models from server
    """
    client = openai.AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        http_client=get_async_client(hass),
    )

    models_response = await client.with_options(timeout=DEFAULT_TIMEOUT).models.list()
    return [
        SelectOptionDict(value=model.id, label=model.id)
        for model in models_response.data
    ]


def _create_model_options(models: list[str]) -> list[SelectOptionDict]:
    """Create SelectOptionDict list from model names.

    Args:
        models: List of model names

    Returns:
        List of SelectOptionDict for use in selectors
    """
    return [SelectOptionDict(value=model, label=model) for model in models]


def _create_model_selector(
    models: list[SelectOptionDict], default_model: str = DEFAULT_MODEL
) -> SelectSelector:
    """Create a model selection selector.

    Args:
        models: List of available models as SelectOptionDict
        default_model: Default model to select

    Returns:
        SelectSelector configured for model selection
    """
    return SelectSelector(
        SelectSelectorConfig(
            options=models,
            mode=SelectSelectorMode.DROPDOWN,
            custom_value=True,
        )
    )


def _create_number_selector(
    mode: NumberSelectorMode,
    min_val: float,
    max_val: float,
    step: float | None = None,
) -> NumberSelector:
    """Create a NumberSelector with specified parameters.

    Args:
        mode: The selector mode (BOX or SLIDER)
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        step: Step size for sliders (optional)

    Returns:
        NumberSelector configured with the specified parameters
    """
    config = NumberSelectorConfig(
        mode=mode,
        min=min_val,
        max=max_val,
    )
    if step is not None:
        config = NumberSelectorConfig(
            mode=mode,
            min=min_val,
            max=max_val,
            step=step,
        )
    return NumberSelector(config)


def _create_max_tokens_selector() -> NumberSelector:
    """Create a NumberSelector for max tokens configuration."""
    return _create_number_selector(
        NumberSelectorMode.BOX, MIN_MAX_TOKENS, MAX_MAX_TOKENS
    )


def _create_temperature_selector() -> NumberSelector:
    """Create a NumberSelector for temperature configuration."""
    return _create_number_selector(
        NumberSelectorMode.SLIDER, MIN_TEMPERATURE, MAX_TEMPERATURE, TEMPERATURE_STEP
    )


def _create_top_p_selector() -> NumberSelector:
    """Create a NumberSelector for top_p configuration."""
    return _create_number_selector(
        NumberSelectorMode.SLIDER, MIN_TOP_P, MAX_TOP_P, TOP_P_STEP
    )


async def _safe_fetch_models_with_errors(
    hass: HomeAssistant,
    base_url: str,
    api_key: str,
) -> tuple[list[SelectOptionDict], dict[str, str]]:
    """Safely fetch models with error handling for config flows.

    Args:
        hass: HomeAssistant instance
        base_url: LM Studio server base URL
        api_key: API key for authentication

    Returns:
        Tuple of (models list, errors dict)
    """
    errors: dict[str, str] = {}
    models: list[SelectOptionDict] = []

    try:
        models = await _fetch_available_models(hass, base_url, api_key)
    except openai.APIConnectionError:
        errors["base"] = "cannot_connect"
    except openai.AuthenticationError:
        errors["base"] = "invalid_auth"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"

    return models, errors


async def _safe_fetch_models(
    hass: HomeAssistant,
    base_url: str,
    api_key: str,
    cached_models: list[str] | None = None,
) -> list[SelectOptionDict]:
    """Safely get models with fallback to cached models.

    Args:
        hass: HomeAssistant instance
        base_url: LM Studio server base URL
        api_key: API key for authentication
        cached_models: Optional cached models to use as fallback

    Returns:
        List of SelectOptionDict for model selection
    """
    # Convert cached models if provided
    if cached_models:
        if isinstance(cached_models[0], str):
            models = _create_model_options(cached_models)
        else:
            models = cached_models
    else:
        models = []

    # Try to fetch fresh models if no cached models or cache empty
    if not models:
        try:
            models = await _fetch_available_models(hass, base_url, api_key)
        except Exception:
            _LOGGER.exception("Failed to fetch models")
            models = []

    return models


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Optional(CONF_API_KEY, default=DEFAULT_API_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> list[str]:
    """Validate the user input allows us to connect and return available models."""
    # Test connection by listing models and return model list
    # Use the same error handling as the config flow for consistency
    models, errors = await _safe_fetch_models_with_errors(
        hass, data[CONF_BASE_URL], data[CONF_API_KEY]
    )
    if errors:
        if errors["base"] == "invalid_auth":
            raise openai.AuthenticationError(
                response=httpx.Response(
                    status_code=401,
                    request=httpx.Request(method="GET", url=data[CONF_BASE_URL]),
                ),
                body=None,
                message="Invalid API key",
            )
        if errors["base"] == "unknown":
            raise openai.APIError(
                request=httpx.Request(method="GET", url=data[CONF_BASE_URL]),
                body=None,
                message="Unknown error",
            )
        raise openai.APIConnectionError(
            request=httpx.Request(method="GET", url=data[CONF_BASE_URL])
        )
    return [model["value"] for model in models]


class LMStudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LM Studio."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._connection_data: dict[str, Any] = {}
        self._available_models: list[SelectOptionDict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        # Prevent duplicate entries for the same base URL
        self._async_abort_entries_match({CONF_BASE_URL: user_input[CONF_BASE_URL]})

        # Use the safe fetch helper
        self._available_models, errors = await _safe_fetch_models_with_errors(
            self.hass, user_input[CONF_BASE_URL], user_input[CONF_API_KEY]
        )

        if not errors:
            # Store connection data and move to model selection
            self._connection_data = user_input
            return await self.async_step_model()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle model selection step."""
        if user_input is not None:
            # Combine connection data with model selection
            data = {**self._connection_data, **user_input}

            return self.async_create_entry(
                title=self._connection_data["base_url"],
                data=data,
                subentries=[
                    {
                        "data": {},
                        "subentry_type": "conversation",
                        "title": f"Conversation - {user_input[CONF_MODEL]}",
                        "unique_id": None,
                    },
                ],
            )

        # Use helper function to create model selector
        schema = vol.Schema(
            {
                vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): _create_model_selector(
                    self._available_models
                ),
            }
        )

        return self.async_show_form(step_id="model", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Return the options flow."""
        return OptionsFlowHandler()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {
            "conversation": ConversationFlowHandler,
        }


class LMStudioSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for LM Studio."""

    def __init__(self) -> None:
        """Initialize subentry flow."""
        super().__init__()
        self._config_entry: ConfigEntry | None = None

    @property
    def config_entry(self) -> ConfigEntry:
        """Get the config entry."""
        if self._config_entry is None:
            entry_id, _ = self.handler
            self._config_entry = self.hass.config_entries.async_get_entry(entry_id)
            if self._config_entry is None:
                raise ValueError("Config entry not found")
        return self._config_entry

    async def _get_available_models(self) -> list[SelectOptionDict]:
        """Get available models from the LM Studio server."""
        return await _safe_fetch_models(
            self.hass,
            self.config_entry.data[CONF_BASE_URL],
            self.config_entry.data[CONF_API_KEY],
        )


class ConversationFlowHandler(LMStudioSubentryFlowHandler):
    """Handle conversation subentry flow."""

    def __init__(self) -> None:
        """Initialize conversation flow handler."""
        super().__init__()
        self._existing_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the user step (entry point for subentry flow)."""
        return await self.async_step_init(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a conversation subentry."""
        # Get the existing subentry data for editing
        subentry = self._get_reconfigure_subentry()
        if subentry:
            # Pre-populate with existing data
            self._existing_data = subentry.data.copy()
        else:
            self._existing_data = {}
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle conversation configuration."""
        if user_input is not None:
            # Create title with model information
            model_name = user_input.get(CONF_MODEL, "Unknown Model")
            title = f"Conversation - {model_name}"

            # Check if we're in a reconfigure flow
            if self.source == "reconfigure":
                # Update existing subentry
                subentry = self._get_reconfigure_subentry()
                return self.async_update_and_abort(
                    entry=self.config_entry,
                    subentry=subentry,
                    title=title,
                    data=user_input,
                )

            # Create new subentry
            return self.async_create_entry(title=title, data=user_input)

        models = await self._get_available_models()

        # Use parent config entry's model as default if available
        default_model = self.config_entry.data.get(CONF_MODEL, DEFAULT_MODEL)

        schema = _create_conversation_schema(
            models=models,
            existing_data=self._existing_data,
            default_model=default_model,
        )

        return self.async_show_form(step_id="init", data_schema=schema)


def _create_conversation_schema(
    models: list[SelectOptionDict],
    existing_data: dict[str, Any] | None = None,
    default_model: str = DEFAULT_MODEL,
    include_name: bool = True,
    include_prompt: bool = True,
    include_llm_api: bool = True,
) -> vol.Schema:
    """Create a conversation configuration schema.

    Args:
        models: Available models for selection
        existing_data: Existing configuration data for defaults
        default_model: Default model if no existing data
        include_name: Whether to include name field
        include_prompt: Whether to include prompt field
        include_llm_api: Whether to include LLM API field

    Returns:
        Schema for conversation configuration
    """
    existing_data = existing_data or {}
    schema_dict: dict[vol.Marker, type | selector.Selector] = {}

    if include_name:
        default_name = existing_data.get(
            CONF_NAME, f"Chat - {DEFAULT_CONVERSATION_NAME}"
        )
        schema_dict[vol.Required(CONF_NAME, default=default_name)] = str

    schema_dict[
        vol.Optional(
            CONF_MODEL,
            default=existing_data.get(CONF_MODEL, default_model),
        )
    ] = _create_model_selector(models)

    if include_prompt:
        schema_dict[
            vol.Optional(
                CONF_PROMPT,
                default=existing_data.get(CONF_PROMPT, DEFAULT_PROMPT),
            )
        ] = TemplateSelector()

    if include_llm_api:
        schema_dict[
            vol.Optional(
                CONF_LLM_HASS_API,
                default=existing_data.get(CONF_LLM_HASS_API, True),
            )
        ] = BooleanSelector()

    schema_dict.update(
        {
            vol.Optional(
                CONF_MAX_TOKENS,
                default=existing_data.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
            ): _create_max_tokens_selector(),
            vol.Optional(
                CONF_TEMPERATURE,
                default=existing_data.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
            ): _create_temperature_selector(),
            vol.Optional(
                CONF_TOP_P,
                default=existing_data.get(CONF_TOP_P, DEFAULT_TOP_P),
            ): _create_top_p_selector(),
        }
    )

    return vol.Schema(schema_dict)


class OptionsFlowHandler(OptionsFlow):
    """Handle options flow for LM Studio."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            # Update the config entry data instead of options
            new_data = self.config_entry.data.copy()
            new_data.update(user_input)

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        # Get available models using helper function
        models = await _safe_fetch_models(
            self.hass,
            self.config_entry.data[CONF_BASE_URL],
            self.config_entry.data[CONF_API_KEY],
            self.config_entry.data.get("available_models"),
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MODEL,
                    default=self.config_entry.data.get(CONF_MODEL, DEFAULT_MODEL),
                ): _create_model_selector(models),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
