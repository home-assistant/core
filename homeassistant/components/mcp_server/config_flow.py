"""Config flow for the Model Context Protocol Server integration."""

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MORE_INFO_URL = "https://www.home-assistant.io/integrations/mcp_server/#configuration"


def _llm_api_names(hass: HomeAssistant) -> dict[str, str]:
    """Return the registered LLM API names keyed by API id."""
    return {api.id: api.name for api in llm.async_get_apis(hass)}


def _llm_api_schema(llm_apis: dict[str, str], default: list[str]) -> vol.Schema:
    """Return the schema for selecting LLM APIs."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_LLM_HASS_API,
                default=default,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(
                            label=name,
                            value=llm_api_id,
                        )
                        for llm_api_id, name in llm_apis.items()
                    ],
                    multiple=True,
                )
            ),
        }
    )


class ModelContextServerProtocolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Model Context Protocol Server."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ModelContextServerProtocolOptionsFlow:
        """Create the options flow."""
        return ModelContextServerProtocolOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        llm_apis = _llm_api_names(self.hass)
        if user_input is not None:
            if not user_input[CONF_LLM_HASS_API]:
                errors[CONF_LLM_HASS_API] = "llm_api_required"
            else:
                return self.async_create_entry(
                    title=", ".join(
                        llm_apis[api_id] for api_id in user_input[CONF_LLM_HASS_API]
                    ),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_llm_api_schema(llm_apis, [llm.LLM_API_ASSIST]),
            description_placeholders={"more_info_url": MORE_INFO_URL},
            errors=errors,
        )


class ModelContextServerProtocolOptionsFlow(OptionsFlow):
    """Handle an options flow to change the exposed LLM APIs."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options step."""
        errors: dict[str, str] = {}
        llm_apis = _llm_api_names(self.hass)
        if user_input is not None:
            if not user_input[CONF_LLM_HASS_API]:
                errors[CONF_LLM_HASS_API] = "llm_api_required"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, **user_input},
                    title=", ".join(
                        llm_apis[api_id] for api_id in user_input[CONF_LLM_HASS_API]
                    ),
                )
                return self.async_create_entry(data={})

        current = [
            api_id
            for api_id in self.config_entry.data.get(CONF_LLM_HASS_API, [])
            if api_id in llm_apis
        ]
        return self.async_show_form(
            step_id="init",
            data_schema=_llm_api_schema(llm_apis, current),
            description_placeholders={"more_info_url": MORE_INFO_URL},
            errors=errors,
        )
