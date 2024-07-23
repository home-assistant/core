"""Config flow for GPSD integration."""

from __future__ import annotations

import socket
from typing import Any

from gps3.agps3threaded import GPSD_PORT as DEFAULT_PORT, HOST as DEFAULT_HOST
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


class GPSDConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GPSD."""

    VERSION = 1

    @staticmethod
    def test_connection(host: str, port: int) -> bool:
        """Test socket connection."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((host, port))
                sock.shutdown(2)
        except OSError:
            return False
        else:
            return True

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._async_abort_entries_match(user_input)

            connected = await self.hass.async_add_executor_job(
                self.test_connection, user_input[CONF_HOST], user_input[CONF_PORT]
            )

            if not connected:
                return self.async_abort(reason="cannot_connect")

            port = ""
            if user_input[CONF_PORT] != DEFAULT_PORT:
                port = f":{user_input[CONF_PORT]}"

            return self.async_create_entry(
                title=user_input.get(CONF_NAME, f"GPS {user_input[CONF_HOST]}{port}"),
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
