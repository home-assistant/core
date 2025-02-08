"""Config flow for Google Generative AI Conversation integration."""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
import logging
from types import MappingProxyType
from typing import Any

from google.ai import generativelanguage_v1beta
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import ClientError, GoogleAPIError
import google.generativeai as genai
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_NAME
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
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
)

_LOGGER = logging.getLogger(__name__)

STEP_API_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)

RECOMMENDED_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = generativelanguage_v1beta.ModelServiceAsyncClient(
        client_options=ClientOptions(api_key=data[CONF_API_KEY])
    )
    await client.list_models(timeout=5.0)


class GoogleGenerativeAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Generative AI Conversation."""

    VERSION = 1

    async def async_step_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except GoogleAPIError as err:
                if isinstance(err, ClientError) and err.reason == "API_KEY_INVALID":
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data=user_input,
                    )
                return self.async_create_entry(
                    title="Google Generative AI",
                    data=user_input,
                    options=RECOMMENDED_OPTIONS,
                )
        return self.async_show_form(
            step_id="api",
            data_schema=STEP_API_DATA_SCHEMA,
            description_placeholders={
                "api_key_url": "https://aistudio.google.com/app/apikey"
            },
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self.async_step_api()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is not None:
            return await self.async_step_api()

        reauth_entry = self._get_reauth_entry()
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                CONF_NAME: reauth_entry.title,
                CONF_API_KEY: reauth_entry.data.get(CONF_API_KEY, ""),
            },
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
        self.last_rendered_recommended = config_entry.options.get(
            CONF_RECOMMENDED, False
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        options: dict[str, Any] | MappingProxyType[str, Any] = self.config_entry.options

        if user_input is not None:
            if user_input[CONF_RECOMMENDED] == self.last_rendered_recommended:
                if user_input[CONF_LLM_HASS_API] == "none":
                    user_input.pop(CONF_LLM_HASS_API)
                return self.async_create_entry(title="", data=user_input)

            # Re-render the options again, now with the recommended options shown/hidden
            self.last_rendered_recommended = user_input[CONF_RECOMMENDED]

            options = {
                CONF_RECOMMENDED: user_input[CONF_RECOMMENDED],
                CONF_PROMPT: user_input[CONF_PROMPT],
                CONF_LLM_HASS_API: user_input[CONF_LLM_HASS_API],
            }

        schema = await google_generative_ai_config_option_schema(self.hass, options)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )


async def google_generative_ai_config_option_schema(
    hass: HomeAssistant,
    options: dict[str, Any] | MappingProxyType[str, Any],
) -> dict:
    """Return a schema for Google Generative AI completion options."""
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

    schema = {
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

    api_models = await hass.async_add_executor_job(partial(genai.list_models))

    models = [
        SelectOptionDict(
            label=api_model.display_name,
            value=api_model.name,
        )
        for api_model in sorted(api_models, key=lambda x: x.display_name)
        if (
            api_model.name != "models/gemini-1.0-pro"  # duplicate of gemini-pro
            and "vision" not in api_model.name
            and "generateContent" in api_model.supported_generation_methods
        )
    ]

    harm_block_thresholds: list[SelectOptionDict] = [
        SelectOptionDict(
            label="Block none",
            value="BLOCK_NONE",
        ),
        SelectOptionDict(
            label="Block few",
            value="BLOCK_ONLY_HIGH",
        ),
        SelectOptionDict(
            label="Block some",
            value="BLOCK_MEDIUM_AND_ABOVE",
        ),
        SelectOptionDict(
            label="Block most",
            value="BLOCK_LOW_AND_ABOVE",
        ),
    ]
    harm_block_thresholds_selector = SelectSelector(
        SelectSelectorConfig(
            mode=SelectSelectorMode.DROPDOWN, options=harm_block_thresholds
        )
    )

    schema.update(
        {
            vol.Optional(
                CONF_CHAT_MODEL,
                description={"suggested_value": options.get(CONF_CHAT_MODEL)},
                default=RECOMMENDED_CHAT_MODEL,
            ): SelectSelector(
                SelectSelectorConfig(mode=SelectSelectorMode.DROPDOWN, options=models)
            ),
            vol.Optional(
                CONF_TEMPERATURE,
                description={"suggested_value": options.get(CONF_TEMPERATURE)},
                default=RECOMMENDED_TEMPERATURE,
            ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
            vol.Optional(
                CONF_TOP_P,
                description={"suggested_value": options.get(CONF_TOP_P)},
                default=RECOMMENDED_TOP_P,
            ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
            vol.Optional(
                CONF_TOP_K,
                description={"suggested_value": options.get(CONF_TOP_K)},
                default=RECOMMENDED_TOP_K,
            ): int,
            vol.Optional(
                CONF_MAX_TOKENS,
                description={"suggested_value": options.get(CONF_MAX_TOKENS)},
                default=RECOMMENDED_MAX_TOKENS,
            ): int,
            vol.Optional(
                CONF_HARASSMENT_BLOCK_THRESHOLD,
                description={
                    "suggested_value": options.get(CONF_HARASSMENT_BLOCK_THRESHOLD)
                },
                default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
            ): harm_block_thresholds_selector,
            vol.Optional(
                CONF_HATE_BLOCK_THRESHOLD,
                description={"suggested_value": options.get(CONF_HATE_BLOCK_THRESHOLD)},
                default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
            ): harm_block_thresholds_selector,
            vol.Optional(
                CONF_SEXUAL_BLOCK_THRESHOLD,
                description={
                    "suggested_value": options.get(CONF_SEXUAL_BLOCK_THRESHOLD)
                },
                default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
            ): harm_block_thresholds_selector,
            vol.Optional(
                CONF_DANGEROUS_BLOCK_THRESHOLD,
                description={
                    "suggested_value": options.get(CONF_DANGEROUS_BLOCK_THRESHOLD)
                },
                default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
            ): harm_block_thresholds_selector,
        }
    )
    return schema
