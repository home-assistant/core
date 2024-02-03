"""Config flow for GPSD integration."""
from __future__ import annotations

import socket
from typing import Any

from gps3.agps3threaded import GPSD_PORT as DEFAULT_PORT, HOST as DEFAULT_HOST
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


class GPSDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GPSD."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._async_abort_entries_match(user_input)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect((user_input[CONF_HOST], user_input[CONF_PORT]))
                sock.shutdown(2)
            except OSError:
                return self.async_abort(reason="cannot_connect")

            port = ""
            if user_input[CONF_PORT] != DEFAULT_PORT:
                port = f":{user_input[CONF_PORT]}"

            return self.async_create_entry(
                title=user_input.get(CONF_NAME, f"GPS {user_input[CONF_HOST]}{port}"),
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
