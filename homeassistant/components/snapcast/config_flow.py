"""Snapcast config flow."""

from __future__ import annotations

import logging
import socket

import snapcast.control
from snapcast.control.server import CONTROL_PORT
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SNAPCAST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=CONTROL_PORT): int,
    }
)


class SnapcastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Snapcast config flow."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle first step."""

        def _show_form(errors=None):
            return self.async_show_form(
                step_id="user",
                data_schema=SNAPCAST_SCHEMA,
                errors=errors,
            )

        if not user_input:
            return _show_form()

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        errors = {}
        client = None

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
            await client.stop()
        finally:
            del client

        if errors:
            return _show_form(errors=errors)

        return self.async_create_entry(
            title=f"{host}:{port}",
            data=user_input,
        )

    async def async_step_import(self, import_config: dict[str, str]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)
