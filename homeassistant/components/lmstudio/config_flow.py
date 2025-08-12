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
    DEFAULT_AI_TASK_NAME,
    DEFAULT_API_KEY,
    DEFAULT_BASE_URL,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CONVERSATION_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Optional(CONF_API_KEY, default=DEFAULT_API_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    client = openai.AsyncOpenAI(
        base_url=data[CONF_BASE_URL],
        api_key=data[CONF_API_KEY],
        http_client=get_async_client(hass),
    )

    # Test connection by listing models
    await client.with_options(timeout=10.0).models.list()


class LMStudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LM Studio."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._connection_data: dict[str, Any] = {}

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
            await validate_input(self.hass, user_input)
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
                title=self._connection_data[CONF_BASE_URL],
                data=data,
                subentries=[
                    {
                        "subentry_type": "conversation",
                        "data": RECOMMENDED_CONVERSATION_OPTIONS,
                        "title": DEFAULT_CONVERSATION_NAME,
                        "unique_id": None,
                    },
                    {
                        "subentry_type": "ai_task_data",
                        "data": RECOMMENDED_AI_TASK_OPTIONS,
                        "title": DEFAULT_AI_TASK_NAME,
                        "unique_id": None,
                    },
                ],
            )

        # Get available models
        models = await self._get_available_models()

        schema = vol.Schema(
            {
                vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): SelectSelector(
                    SelectSelectorConfig(
                        options=models,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="model", data_schema=schema)

    async def _get_available_models(self) -> list[SelectOptionDict]:
        """Get available models from the LM Studio server."""
        try:
            client = openai.AsyncOpenAI(
                base_url=self._connection_data[CONF_BASE_URL],
                api_key=self._connection_data[CONF_API_KEY],
                http_client=get_async_client(self.hass),
            )
            models = await client.with_options(timeout=10.0).models.list()
            return [
                SelectOptionDict(value=model.id, label=model.id)
                for model in models.data
            ]
        except Exception:
            _LOGGER.exception("Failed to fetch models")
            return []

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
            "ai_task_data": AITaskDataFlowHandler,
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
            client = openai.AsyncOpenAI(
                base_url=self.config_entry.data[CONF_BASE_URL],
                api_key=self.config_entry.data[CONF_API_KEY],
                http_client=get_async_client(self.hass),
            )
            models = await client.with_options(timeout=10.0).models.list()
            return [
                SelectOptionDict(value=model.id, label=model.id)
                for model in models.data
            ]
        except Exception:
            _LOGGER.exception("Failed to fetch models")
            return []


class ConversationFlowHandler(LMStudioSubentryFlowHandler):
    """Handle conversation subentry flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle conversation configuration."""
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        models = await self._get_available_models()

        # Use parent config entry's model as default if available
        default_model = self.config_entry.data.get(CONF_MODEL, DEFAULT_MODEL)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_CONVERSATION_NAME): str,
                vol.Optional(CONF_MODEL, default=default_model): SelectSelector(
                    SelectSelectorConfig(
                        options=models,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
                vol.Optional(CONF_PROMPT): TemplateSelector(),
                vol.Optional(CONF_LLM_HASS_API, default=False): BooleanSelector(),
                vol.Optional(
                    CONF_MAX_TOKENS, default=DEFAULT_MAX_TOKENS
                ): NumberSelector(
                    NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=8192)
                ),
                vol.Optional(
                    CONF_TEMPERATURE, default=DEFAULT_TEMPERATURE
                ): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.SLIDER, min=0.0, max=2.0, step=0.1
                    )
                ),
                vol.Optional(CONF_TOP_P, default=DEFAULT_TOP_P): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.SLIDER, min=0.0, max=1.0, step=0.05
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)


class AITaskDataFlowHandler(LMStudioSubentryFlowHandler):
    """Handle AI task data subentry flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle AI task configuration."""
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        models = await self._get_available_models()

        # Use parent config entry's model as default if available
        default_model = self.config_entry.data.get(CONF_MODEL, DEFAULT_MODEL)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_AI_TASK_NAME): str,
                vol.Optional(CONF_MODEL, default=default_model): SelectSelector(
                    SelectSelectorConfig(
                        options=models,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
                vol.Optional(CONF_MAX_TOKENS, default=500): NumberSelector(
                    NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=8192)
                ),
                vol.Optional(CONF_TEMPERATURE, default=0.3): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.SLIDER, min=0.0, max=2.0, step=0.1
                    )
                ),
                vol.Optional(CONF_TOP_P, default=0.95): NumberSelector(
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
            return self.async_create_entry(title="", data=user_input)

        models = await self._get_available_models()

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

    async def _get_available_models(self) -> list[SelectOptionDict]:
        """Get available models from the LM Studio server."""
        try:
            client = openai.AsyncOpenAI(
                base_url=self.config_entry.data[CONF_BASE_URL],
                api_key=self.config_entry.data[CONF_API_KEY],
                http_client=get_async_client(self.hass),
            )
            models = await client.with_options(timeout=10.0).models.list()
            return [
                SelectOptionDict(value=model.id, label=model.id)
                for model in models.data
            ]
        except Exception:
            _LOGGER.exception("Failed to fetch models")
            return []
