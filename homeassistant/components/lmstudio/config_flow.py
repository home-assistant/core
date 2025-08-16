"""Config flow for LM Studio integration."""

from __future__ import annotations

import logging
from typing import Any

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
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DOMAIN,
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

    models_response = await client.with_options(timeout=10.0).models.list()
    return [
        SelectOptionDict(value=model.id, label=model.id)
        for model in models_response.data
    ]


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
    models = await _fetch_available_models(
        hass, data[CONF_BASE_URL], data[CONF_API_KEY]
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
        self._available_models: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors: dict[str, str] = {}

        # Prevent duplicate entries for the same base URL
        self._async_abort_entries_match({CONF_BASE_URL: user_input[CONF_BASE_URL]})

        try:
            self._available_models = await validate_input(self.hass, user_input)
        except openai.APIConnectionError:
            errors["base"] = "cannot_connect"
        except openai.AuthenticationError:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
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

        # Create model selection options from available models
        model_options = [
            SelectOptionDict(value=model, label=model)
            for model in self._available_models
        ]

        schema = vol.Schema(
            {
                vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): SelectSelector(
                    SelectSelectorConfig(
                        options=model_options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
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
        try:
            return await _fetch_available_models(
                self.hass,
                self.config_entry.data[CONF_BASE_URL],
                self.config_entry.data[CONF_API_KEY],
            )
        except Exception:
            _LOGGER.exception("Failed to fetch models")
            return []


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
            return self.async_create_entry(title=title, data=user_input)

        models = await self._get_available_models()

        # Use parent config entry's model as default if available
        default_model = self.config_entry.data.get(CONF_MODEL, DEFAULT_MODEL)

        # Create default name with Chat prefix, or use existing data
        default_name = self._existing_data.get(
            CONF_NAME, f"Chat - {DEFAULT_CONVERSATION_NAME}"
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=default_name): str,
                vol.Optional(
                    CONF_MODEL,
                    default=self._existing_data.get(CONF_MODEL, default_model),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=models,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
                vol.Optional(
                    CONF_PROMPT, default=self._existing_data.get(CONF_PROMPT, "")
                ): TemplateSelector(),
                vol.Optional(
                    CONF_LLM_HASS_API,
                    default=self._existing_data.get(CONF_LLM_HASS_API, False),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_MAX_TOKENS,
                    default=self._existing_data.get(
                        CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=8192)
                ),
                vol.Optional(
                    CONF_TEMPERATURE,
                    default=self._existing_data.get(
                        CONF_TEMPERATURE, DEFAULT_TEMPERATURE
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.SLIDER, min=0.0, max=2.0, step=0.1
                    )
                ),
                vol.Optional(
                    CONF_TOP_P,
                    default=self._existing_data.get(CONF_TOP_P, DEFAULT_TOP_P),
                ): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.SLIDER, min=0.0, max=1.0, step=0.05
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)


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

        # Get available models from stored data (from initial setup)
        available_models = self.config_entry.data.get("available_models", [])

        # Convert to SelectOptionDict format if needed
        if available_models and isinstance(available_models[0], str):
            models = [
                SelectOptionDict(value=model, label=model) for model in available_models
            ]
        else:
            models = available_models

        # If no stored models, try to fetch them dynamically
        if not models:
            try:
                models = await _fetch_available_models(
                    self.hass,
                    self.config_entry.data[CONF_BASE_URL],
                    self.config_entry.data[CONF_API_KEY],
                )
            except Exception:
                _LOGGER.exception("Failed to fetch models for options")
                models = []

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MODEL,
                    default=self.config_entry.data.get(CONF_MODEL, DEFAULT_MODEL),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=models,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
