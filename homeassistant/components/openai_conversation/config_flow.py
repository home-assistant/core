"""Config flow for OpenAI Conversation integration."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

import openai
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
from homeassistant.helpers.typing import VolDictType

from .const import (
    CONF_AZURE_API_VERSION,
    CONF_AZURE_ENDPOINT,
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_PROVIDER,
    CONF_REASONING_EFFORT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DOMAIN,
    LOGGER,
    PROVIDER_AZURE_OPENAI,
    PROVIDER_OPENAI,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    UNSUPPORTED_MODELS,
)

_LOGGER = logging.getLogger(__name__)

STEP_PROVIDER_SELECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PROVIDER): vol.In([PROVIDER_OPENAI, PROVIDER_AZURE_OPENAI]),
    }
)

STEP_OPENAI_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)

STEP_AZURE_OPENAI_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AZURE_ENDPOINT): str,
        vol.Required(CONF_API_KEY): str,
    }
)

RECOMMENDED_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}


async def check_openai_connection(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    client = openai.AsyncOpenAI(api_key=data[CONF_API_KEY])
    result = await hass.async_add_executor_job(
        client.with_options(timeout=10.0).models.list
    )
    LOGGER.info("OpenAI models: %s", result)


async def check_azure_openai_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> None:
    """Validate the user input allows us to connect."""
    client = openai.AsyncAzureOpenAI(
        azure_endpoint=data[CONF_AZURE_ENDPOINT],
        api_key=data[CONF_API_KEY],
        api_version=CONF_AZURE_API_VERSION,
    )
    result = await hass.async_add_executor_job(
        client.with_options(timeout=10.0).models.list
    )

    models = [model async for model in result]

    LOGGER.info("Azure OpenAI models: %s", models)


class OpenAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenAI Conversation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user", menu_options=["openai", "azure_openai"]
        )

    async def async_step_openai(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the OpenAI step."""
        if user_input is None:
            return self.async_show_form(
                step_id="openai",
                data_schema=STEP_OPENAI_USER_DATA_SCHEMA,
            )

        errors: dict[str, str] = {}

        try:
            await check_openai_connection(self.hass, user_input)
        except openai.APIConnectionError:
            errors["base"] = "cannot_connect"
        except openai.AuthenticationError:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title="ChatGPT",
                data=user_input,
                options=RECOMMENDED_OPTIONS,
            )

        return self.async_show_form(
            step_id="openai", data_schema=STEP_OPENAI_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_azure_openai(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the Azure OpenAI step."""
        if user_input is None:
            return self.async_show_form(
                step_id="azure_openai",
                data_schema=STEP_AZURE_OPENAI_USER_DATA_SCHEMA,
            )

        errors = {}
        try:
            await check_azure_openai_connection(self.hass, user_input)
        except openai.APIConnectionError:
            errors["base"] = "cannot_connect"
        except openai.AuthenticationError:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title="Azure ChatGPT",
                data=user_input,
                options=RECOMMENDED_OPTIONS,
            )

        return self.async_show_form(
            step_id="azure_openai",
            data_schema=STEP_AZURE_OPENAI_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OpenAIOptionsFlow(config_entry)


class OpenAIOptionsFlow(OptionsFlow):
    """OpenAI config flow options handler."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.last_rendered_recommended = config_entry.options.get(
            CONF_RECOMMENDED, False
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        options: dict[str, Any] | MappingProxyType[str, Any] = self.config_entry.options
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input[CONF_RECOMMENDED] == self.last_rendered_recommended:
                if user_input[CONF_LLM_HASS_API] == "none":
                    user_input.pop(CONF_LLM_HASS_API)

                if user_input.get(CONF_CHAT_MODEL) in UNSUPPORTED_MODELS:
                    errors[CONF_CHAT_MODEL] = "model_not_supported"
                else:
                    return self.async_create_entry(title="", data=user_input)
            else:
                # Re-render the options again, now with the recommended options shown/hidden
                self.last_rendered_recommended = user_input[CONF_RECOMMENDED]

                options = {
                    CONF_RECOMMENDED: user_input[CONF_RECOMMENDED],
                    CONF_PROMPT: user_input[CONF_PROMPT],
                    CONF_LLM_HASS_API: user_input[CONF_LLM_HASS_API],
                }

        schema = openai_config_option_schema(self.hass, options)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
        )


def openai_config_option_schema(
    hass: HomeAssistant,
    options: dict[str, Any] | MappingProxyType[str, Any],
) -> VolDictType:
    """Return a schema for OpenAI completion options."""
    hass_apis: list[SelectOptionDict] = [
        SelectOptionDict(
            label="No control",
            value="none",
        )
    ]
    hass_apis.extend(
        SelectOptionDict(
            label=api.name,
            value=api.id,
        )
        for api in llm.async_get_apis(hass)
    )

    schema: VolDictType = {
        vol.Optional(
            CONF_PROMPT,
            description={
                "suggested_value": options.get(
                    CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                )
            },
        ): TemplateSelector(),
        vol.Optional(
            CONF_LLM_HASS_API,
            description={"suggested_value": options.get(CONF_LLM_HASS_API)},
            default="none",
        ): SelectSelector(SelectSelectorConfig(options=hass_apis)),
        vol.Required(
            CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, False)
        ): bool,
    }

    if options.get(CONF_RECOMMENDED):
        return schema

    schema.update(
        {
            vol.Optional(
                CONF_CHAT_MODEL,
                description={"suggested_value": options.get(CONF_CHAT_MODEL)},
                default=RECOMMENDED_CHAT_MODEL,
            ): str,
            vol.Optional(
                CONF_MAX_TOKENS,
                description={"suggested_value": options.get(CONF_MAX_TOKENS)},
                default=RECOMMENDED_MAX_TOKENS,
            ): int,
            vol.Optional(
                CONF_TOP_P,
                description={"suggested_value": options.get(CONF_TOP_P)},
                default=RECOMMENDED_TOP_P,
            ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
            vol.Optional(
                CONF_TEMPERATURE,
                description={"suggested_value": options.get(CONF_TEMPERATURE)},
                default=RECOMMENDED_TEMPERATURE,
            ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
            vol.Optional(
                CONF_REASONING_EFFORT,
                description={"suggested_value": options.get(CONF_REASONING_EFFORT)},
                default=RECOMMENDED_REASONING_EFFORT,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=["low", "medium", "high"],
                    translation_key="reasoning_effort",
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )
    return schema
