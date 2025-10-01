"""Config flow for the Model Context Protocol Server integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol  # type: ignore[import-untyped]

from homeassistant import config_entries  # type: ignore[import-untyped]
from homeassistant.const import CONF_LLM_HASS_API  # type: ignore[import-untyped]
from homeassistant.core import HomeAssistant  # type: ignore[import-untyped]
from homeassistant.helpers import llm  # type: ignore[import-untyped]
from homeassistant.helpers.selector import (  # type: ignore[import-untyped]
    SelectSelector,
    SelectSelectorConfig,
)

from .const import DOMAIN

MORE_INFO_URL = "https://www.home-assistant.io/integrations/mcp_server/#configuration"


class ModelContextServerProtocolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Allow users to select which LLM APIs are exposed through MCP."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Handle the initial step of the config flow."""

        llm_apis = {api.id: api.name for api in llm.async_get_apis(self.hass)}
        selector = SelectSelector(
            SelectSelectorConfig(options=[{"value": api_id, "label": name} for api_id, name in llm_apis.items()], multiple=True)
        )

        if user_input is not None:
            selection = user_input.get(CONF_LLM_HASS_API, [])
            if isinstance(selection, str):
                selection = [selection]

            if not selection:
                errors = {CONF_LLM_HASS_API: "llm_api_required"}
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Model Context Protocol", data={CONF_LLM_HASS_API: selection})
        else:
            errors = {}

        if not llm_apis:
            errors = {CONF_LLM_HASS_API: "llm_api_required"}

        data_schema = vol.Schema(
            {
                vol.Required(CONF_LLM_HASS_API): selector,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"more_info_url": MORE_INFO_URL},
        )
