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
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_REQUIRE_ADMIN, DOMAIN

_LOGGER = logging.getLogger(__name__)

MORE_INFO_URL = "https://www.home-assistant.io/integrations/mcp_server/#configuration"


def _llm_api_names(hass: HomeAssistant) -> dict[str, str]:
    """Return the registered LLM API names keyed by API id."""
    return {api.id: api.name for api in llm.async_get_apis(hass)}


def _llm_api_title(llm_apis: dict[str, str], api_ids: list[str]) -> str:
    """Return the entry title generated for the selected LLM APIs."""
    return ", ".join(llm_apis[api_id] for api_id in api_ids if api_id in llm_apis)


def _selected_llm_apis(entry: ConfigEntry, llm_apis: dict[str, str]) -> list[str]:
    """Return the still registered LLM APIs selected by the config entry."""
    api_ids = entry.data.get(CONF_LLM_HASS_API) or []
    if isinstance(api_ids, str):  # Old config entries stored a single API
        api_ids = [api_ids]
    return [api_id for api_id in api_ids if api_id in llm_apis]


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


def _options_schema(
    llm_apis: dict[str, str], default: list[str], require_admin: bool
) -> vol.Schema:
    """Return the schema for the options flow."""
    return _llm_api_schema(llm_apis, default).extend(
        {
            vol.Required(CONF_REQUIRE_ADMIN, default=require_admin): BooleanSelector(),
        }
    )


class ModelContextServerProtocolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Model Context Protocol Server."""

    VERSION = 1
    MINOR_VERSION = 2

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
                    title=_llm_api_title(llm_apis, user_input[CONF_LLM_HASS_API]),
                    data={**user_input, CONF_REQUIRE_ADMIN: True},
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
        current = _selected_llm_apis(self.config_entry, llm_apis)
        if user_input is not None:
            if not user_input[CONF_LLM_HASS_API]:
                errors[CONF_LLM_HASS_API] = "llm_api_required"
            else:
                updates: dict[str, Any] = {
                    "data": {**self.config_entry.data, **user_input}
                }
                # Keep a title the user renamed, only refresh a generated one.
                if self.config_entry.title == _llm_api_title(llm_apis, current):
                    updates["title"] = _llm_api_title(
                        llm_apis, user_input[CONF_LLM_HASS_API]
                    )
                self.hass.config_entries.async_update_entry(
                    self.config_entry, **updates
                )
                # An open SSE session keeps serving the APIs it started with.
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(
                llm_apis,
                current,
                # A disabled config entry has not migrated yet
                self.config_entry.data.get(CONF_REQUIRE_ADMIN, False),
            ),
            description_placeholders={"more_info_url": MORE_INFO_URL},
            errors=errors,
        )
