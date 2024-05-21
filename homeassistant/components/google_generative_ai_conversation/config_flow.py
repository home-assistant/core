"""Config flow for Google Generative AI Conversation integration."""

from __future__ import annotations

from functools import partial
import logging
from types import MappingProxyType
from typing import Any

from google.api_core.exceptions import ClientError
import google.generativeai as genai
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
)

from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    genai.configure(api_key=data[CONF_API_KEY])
    await hass.async_add_executor_job(partial(genai.list_models))


class GoogleGenerativeAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Generative AI Conversation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except ClientError as err:
            if err.reason == "API_KEY_INVALID":
                errors["base"] = "invalid_auth"
            else:
                errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title="Google Generative AI",
                data=user_input,
                options={CONF_LLM_HASS_API: llm.LLM_API_ASSIST},
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return GoogleGenerativeAIOptionsFlow(config_entry)


class GoogleGenerativeAIOptionsFlow(OptionsFlow):
    """Google Generative AI config flow options handler."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input[CONF_LLM_HASS_API] == "none":
                user_input.pop(CONF_LLM_HASS_API)
            return self.async_create_entry(title="", data=user_input)
        schema = await google_generative_ai_config_option_schema(
            self.hass, self.config_entry.options
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )


async def google_generative_ai_config_option_schema(
    hass: HomeAssistant,
    options: MappingProxyType[str, Any],
) -> dict:
    """Return a schema for Google Generative AI completion options."""
    api_models = await hass.async_add_executor_job(partial(genai.list_models))

    models: list[SelectOptionDict] = [
        SelectOptionDict(
            label="Gemini 1.5 Flash (recommended)",
            value="models/gemini-1.5-flash-latest",
        ),
    ]
    models.extend(
        SelectOptionDict(
            label=api_model.display_name,
            value=api_model.name,
        )
        for api_model in sorted(api_models, key=lambda x: x.display_name)
        if (
            api_model.name
            not in (
                "models/gemini-1.0-pro",  # duplicate of gemini-pro
                "models/gemini-1.5-flash-latest",
            )
            and "vision" not in api_model.name
            and "generateContent" in api_model.supported_generation_methods
        )
    )

    apis: list[SelectOptionDict] = [
        SelectOptionDict(
            label="No control",
            value="none",
        )
    ]
    apis.extend(
        SelectOptionDict(
            label=api.name,
            value=api.id,
        )
        for api in llm.async_get_apis(hass)
    )

    return {
        vol.Optional(
            CONF_CHAT_MODEL,
            description={"suggested_value": options.get(CONF_CHAT_MODEL)},
            default=DEFAULT_CHAT_MODEL,
        ): SelectSelector(
            SelectSelectorConfig(
                mode=SelectSelectorMode.DROPDOWN,
                options=models,
            )
        ),
        vol.Optional(
            CONF_LLM_HASS_API,
            description={"suggested_value": options.get(CONF_LLM_HASS_API)},
            default="none",
        ): SelectSelector(SelectSelectorConfig(options=apis)),
        vol.Optional(
            CONF_PROMPT,
            description={"suggested_value": options.get(CONF_PROMPT)},
            default=DEFAULT_PROMPT,
        ): TemplateSelector(),
        vol.Optional(
            CONF_TEMPERATURE,
            description={"suggested_value": options.get(CONF_TEMPERATURE)},
            default=DEFAULT_TEMPERATURE,
        ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
        vol.Optional(
            CONF_TOP_P,
            description={"suggested_value": options.get(CONF_TOP_P)},
            default=DEFAULT_TOP_P,
        ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
        vol.Optional(
            CONF_TOP_K,
            description={"suggested_value": options.get(CONF_TOP_K)},
            default=DEFAULT_TOP_K,
        ): int,
        vol.Optional(
            CONF_MAX_TOKENS,
            description={"suggested_value": options.get(CONF_MAX_TOKENS)},
            default=DEFAULT_MAX_TOKENS,
        ): int,
    }
