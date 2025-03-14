"""Snapcast config flow."""

from __future__ import annotations

import logging
import socket

import snapcast.control
from snapcast.control.server import CONTROL_PORT
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_TITLE, DOMAIN

_LOGGER = logging.getLogger(__name__)

SNAPCAST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=CONTROL_PORT): int,
    }
)


class SnapcastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Snapcast config flow."""

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle first step."""
        errors = {}
        if user_input:
            self._async_abort_entries_match(user_input)
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Attempt to create the server - make sure it's going to work
            try:
                client = await snapcast.control.create_server(
                    self.hass.loop, host, port, reconnect=False
                )
            except socket.gaierror:
                errors["base"] = "invalid_host"
            except OSError:
                errors["base"] = "cannot_connect"
            else:
                client.stop()
                return self.async_create_entry(title=DEFAULT_TITLE, data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=SNAPCAST_SCHEMA, errors=errors
        )
