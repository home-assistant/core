"""Config flow for the Model Context Protocol Server integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import DOMAIN, TITLE

MORE_INFO_URL = "https://www.home-assistant.io/integrations/mcp_server/#configuration"


class ModelContextServerProtocolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Allow users to select which LLM APIs are exposed through MCP."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step of the config flow."""

        llm_apis = {api.id: api.name for api in llm.async_get_apis(self.hass)}
        options: list[SelectOptionDict] = [
            SelectOptionDict(value=api_id, label=name)
            for api_id, name in llm_apis.items()
        ]
        selector = SelectSelector(
            SelectSelectorConfig(
                options=options,
                multiple=True,
            )
        )

        default_selection: list[str] | None = None
        if llm_apis:
            default_selection = [next(iter(llm_apis))]

        if user_input is not None:
            selection = user_input.get(CONF_LLM_HASS_API)
            if isinstance(selection, str):
                selection = [selection]
            elif selection is None:
                selection = []

            selection = [api_id for api_id in selection if api_id in llm_apis]

            if not selection and default_selection is not None:
                selection = default_selection.copy()

            if not selection:
                errors = {CONF_LLM_HASS_API: "llm_api_required"}
            else:
                unique_selection = list(dict.fromkeys(selection))
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                title = (
                    llm_apis[unique_selection[0]]
                    if len(unique_selection) == 1
                    else TITLE
                )
                return self.async_create_entry(
                    title=title, data={CONF_LLM_HASS_API: unique_selection}
                )
        else:
            errors = {}

        if not llm_apis:
            errors = {CONF_LLM_HASS_API: "llm_api_required"}

        schema_default = (
            vol.UNDEFINED if default_selection is None else default_selection
        )
        data_schema = vol.Schema(
            {
                vol.Required(CONF_LLM_HASS_API, default=schema_default): selector,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"more_info_url": MORE_INFO_URL},
        )
