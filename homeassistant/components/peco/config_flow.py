"""Config flow for PECO Outage Counter integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_COUNTY, COUNTY_LIST, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COUNTY): vol.In(COUNTY_LIST),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PECO Outage Counter."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        county = user_input[CONF_COUNTY]

        await self.async_set_unique_id(county)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{county.capitalize()} Outage Count", data=user_input
        )
