"""Config flows for greeneye_monitor."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_PORT
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN


class GreeneyeMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for greeneye_monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Create a config entry from UI."""
        if await self.async_set_unique_id(DOMAIN):
            self._abort_if_unique_id_configured()

        if user_input is not None:
            data = {CONF_PORT: user_input[CONF_PORT]}
            return self.async_create_entry(title="GreenEye Monitor", data=data)

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_PORT): cv.port})
        )
