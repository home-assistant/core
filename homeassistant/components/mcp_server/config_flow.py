"""Config flow for the Model Context Protocol Server integration."""

import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.helpers import llm
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import DOMAIN
from .http import async_get_mcp_server_path
from .types import MCPServerConfigEntry

_LOGGER = logging.getLogger(__name__)

MORE_INFO_URL = "https://www.home-assistant.io/integrations/mcp_server/#configuration"


class ModelContextServerProtocolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Model Context Protocol Server."""

    VERSION = 1
    MINOR_VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_LLM_HASS_API]:
                errors[CONF_LLM_HASS_API] = "llm_api_required"
            else:
                self._async_abort_entries_match(
                    {CONF_LLM_HASS_API: user_input[CONF_LLM_HASS_API]}
                )
                return self.async_create_entry(
                    title=self._async_title(user_input[CONF_LLM_HASS_API]),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._async_schema(),
            description_placeholders={"more_info_url": MORE_INFO_URL},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing config entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            if not user_input[CONF_LLM_HASS_API]:
                errors[CONF_LLM_HASS_API] = "llm_api_required"
            else:
                self._async_abort_entries_match(
                    {CONF_LLM_HASS_API: user_input[CONF_LLM_HASS_API]}
                )
                return self.async_update_reload_and_abort(
                    entry,
                    title=self._async_title(user_input[CONF_LLM_HASS_API]),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._async_schema(entry.data.get(CONF_LLM_HASS_API)),
            description_placeholders=self._async_url_placeholders(entry),
            errors=errors,
        )

    def _async_title(self, llm_api_ids: list[str]) -> str:
        """Return the config entry title for the selected APIs."""
        llm_apis = {api.id: api.name for api in llm.async_get_apis(self.hass)}
        return ", ".join(llm_apis.get(api_id, api_id) for api_id in llm_api_ids)

    def _async_schema(self, default: list[str] | None = None) -> vol.Schema:
        """Return the schema for selecting the LLM APIs to expose."""
        if not default:
            default = [llm.LLM_API_ASSIST]
        llm_apis = {api.id: api.name for api in llm.async_get_apis(self.hass)}
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

    def _async_url_placeholders(self, entry: MCPServerConfigEntry) -> dict[str, str]:
        """Return description placeholders with the URLs serving the entry."""
        path = async_get_mcp_server_path(entry)
        return {
            "more_info_url": MORE_INFO_URL,
            "internal_url": self._async_url(path, external=False),
            "external_url": self._async_url(path, external=True),
        }

    def _async_url(self, path: str, *, external: bool) -> str:
        """Return the internal or external URL serving the given path."""
        try:
            base_url = get_url(
                self.hass,
                allow_internal=not external,
                allow_external=external,
            )
        except NoURLAvailableError:
            return "-"
        return f"{base_url}{path}"
