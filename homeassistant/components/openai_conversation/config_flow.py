"""Config flow for OpenAI Conversation integration."""

from __future__ import annotations

import json
import logging
from typing import Any

import openai
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components.zone import ENTITY_ID_HOME
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    CONF_LLM_HASS_API,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.httpx_client import get_async_client
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
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    RECOMMENDED_WEB_SEARCH,
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
    RECOMMENDED_WEB_SEARCH_USER_LOCATION,
    UNSUPPORTED_MODELS,
    WEB_SEARCH_MODELS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)

RECOMMENDED_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = openai.AsyncOpenAI(
        api_key=data[CONF_API_KEY], http_client=get_async_client(hass)
    )
    await hass.async_add_executor_job(client.with_options(timeout=10.0).models.list)


class OpenAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenAI Conversation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors: dict[str, str] = {}

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
            return self.async_create_entry(
                title="ChatGPT",
                data=user_input,
                options=RECOMMENDED_OPTIONS,
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
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
        self.options = config_entry.options.copy()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage initial options."""
        options = self.options

        hass_apis: list[SelectOptionDict] = [
            SelectOptionDict(
                label=api.name,
                value=api.id,
            )
            for api in llm.async_get_apis(self.hass)
        ]
        if (suggested_llm_apis := options.get(CONF_LLM_HASS_API)) and isinstance(
            suggested_llm_apis, str
        ):
            options[CONF_LLM_HASS_API] = [suggested_llm_apis]

        step_schema: VolDictType = {
            vol.Optional(
                CONF_PROMPT,
                description={"suggested_value": llm.DEFAULT_INSTRUCTIONS_PROMPT},
            ): TemplateSelector(),
            vol.Optional(CONF_LLM_HASS_API): SelectSelector(
                SelectSelectorConfig(options=hass_apis, multiple=True)
            ),
            vol.Required(
                CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, False)
            ): bool,
        }

        if user_input is not None:
            if not user_input.get(CONF_LLM_HASS_API):
                user_input.pop(CONF_LLM_HASS_API, None)

            if user_input[CONF_RECOMMENDED]:
                return self.async_create_entry(title="", data=user_input)

            options.update(user_input)
            if CONF_LLM_HASS_API in options and CONF_LLM_HASS_API not in user_input:
                options.pop(CONF_LLM_HASS_API)
            return await self.async_step_advanced()

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(step_schema), options
            ),
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage advanced options."""
        options = self.options
        errors: dict[str, str] = {}

        step_schema: VolDictType = {
            vol.Optional(
                CONF_CHAT_MODEL,
                default=RECOMMENDED_CHAT_MODEL,
            ): str,
            vol.Optional(
                CONF_MAX_TOKENS,
                default=RECOMMENDED_MAX_TOKENS,
            ): int,
            vol.Optional(
                CONF_TOP_P,
                default=RECOMMENDED_TOP_P,
            ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
            vol.Optional(
                CONF_TEMPERATURE,
                default=RECOMMENDED_TEMPERATURE,
            ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
        }

        if user_input is not None:
            options.update(user_input)
            if user_input.get(CONF_CHAT_MODEL) in UNSUPPORTED_MODELS:
                errors[CONF_CHAT_MODEL] = "model_not_supported"

            if not errors:
                return await self.async_step_model()

        return self.async_show_form(
            step_id="advanced",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(step_schema), options
            ),
            errors=errors,
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage model-specific options."""
        options = self.options
        errors: dict[str, str] = {}

        step_schema: VolDictType = {}

        model = options[CONF_CHAT_MODEL]

        if model.startswith("o"):
            step_schema.update(
                {
                    vol.Optional(
                        CONF_REASONING_EFFORT,
                        default=RECOMMENDED_REASONING_EFFORT,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["low", "medium", "high"],
                            translation_key=CONF_REASONING_EFFORT,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        elif CONF_REASONING_EFFORT in options:
            options.pop(CONF_REASONING_EFFORT)

        if model.startswith(tuple(WEB_SEARCH_MODELS)):
            step_schema.update(
                {
                    vol.Optional(
                        CONF_WEB_SEARCH,
                        default=RECOMMENDED_WEB_SEARCH,
                    ): bool,
                    vol.Optional(
                        CONF_WEB_SEARCH_CONTEXT_SIZE,
                        default=RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["low", "medium", "high"],
                            translation_key=CONF_WEB_SEARCH_CONTEXT_SIZE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_WEB_SEARCH_USER_LOCATION,
                        default=RECOMMENDED_WEB_SEARCH_USER_LOCATION,
                    ): bool,
                }
            )
        elif CONF_WEB_SEARCH in options:
            options = {
                k: v
                for k, v in options.items()
                if k
                not in (
                    CONF_WEB_SEARCH,
                    CONF_WEB_SEARCH_CONTEXT_SIZE,
                    CONF_WEB_SEARCH_USER_LOCATION,
                    CONF_WEB_SEARCH_CITY,
                    CONF_WEB_SEARCH_REGION,
                    CONF_WEB_SEARCH_COUNTRY,
                    CONF_WEB_SEARCH_TIMEZONE,
                )
            }

        if not step_schema:
            return self.async_create_entry(title="", data=options)

        if user_input is not None:
            if user_input.get(CONF_WEB_SEARCH):
                if user_input.get(CONF_WEB_SEARCH_USER_LOCATION):
                    user_input.update(await self._get_location_data())
                else:
                    options.pop(CONF_WEB_SEARCH_CITY, None)
                    options.pop(CONF_WEB_SEARCH_REGION, None)
                    options.pop(CONF_WEB_SEARCH_COUNTRY, None)
                    options.pop(CONF_WEB_SEARCH_TIMEZONE, None)

            options.update(user_input)
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="model",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(step_schema), options
            ),
            errors=errors,
        )

    async def _get_location_data(self) -> dict[str, str]:
        """Get approximate location data of the user."""
        location_data: dict[str, str] = {}
        zone_home = self.hass.states.get(ENTITY_ID_HOME)
        if zone_home is not None:
            client = openai.AsyncOpenAI(
                api_key=self.config_entry.data[CONF_API_KEY],
                http_client=get_async_client(self.hass),
            )
            location_schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_WEB_SEARCH_CITY,
                        description="Free text input for the city, e.g. `San Francisco`",
                    ): str,
                    vol.Optional(
                        CONF_WEB_SEARCH_REGION,
                        description="Free text input for the region, e.g. `California`",
                    ): str,
                }
            )
            response = await client.responses.create(
                model=RECOMMENDED_CHAT_MODEL,
                input=[
                    {
                        "role": "system",
                        "content": "Where are the following coordinates located: "
                        f"({zone_home.attributes[ATTR_LATITUDE]},"
                        f" {zone_home.attributes[ATTR_LONGITUDE]})?",
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "approximate_location",
                        "description": "Approximate location data of the user "
                        "for refined web search results",
                        "schema": convert(location_schema),
                        "strict": False,
                    }
                },
                store=False,
            )
            location_data = location_schema(json.loads(response.output_text) or {})

        if self.hass.config.country:
            location_data[CONF_WEB_SEARCH_COUNTRY] = self.hass.config.country
        location_data[CONF_WEB_SEARCH_TIMEZONE] = self.hass.config.time_zone

        _LOGGER.debug("Location data: %s", location_data)

        return location_data
