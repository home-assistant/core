"""Config flow for OpenHardwareMonitor integration."""

from __future__ import annotations
from typing import Any

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import *

class OpenHardwareMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenHardwareMonitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        data_schema = vol.Schema(
            {vol.Required(CONF_HOST): cv.string, 
             vol.Optional(CONF_PORT, default=8085): cv.port,
             vol.Optional(GROUP_DEVICES_PER_DEPTH_LEVEL, default=2): int}
        )
        if user_input is None:
            return self.async_show_form(data_schema=data_schema)

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]

        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{host}:{port}",
            data=user_input,
        )
