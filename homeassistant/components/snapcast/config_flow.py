"""Snapcast config flow."""

from __future__ import annotations

import logging
import socket

import snapcast.control
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

SNAPCAST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class SnapcastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Snapcast config flow."""

    async def async_step_user(self, user_input=None):
        """Handle first step."""

        def _show_form(errors={}):
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

        # Attempt to create the server - make sure it's going to work
        try:
            client = await snapcast.control.create_server(
                self.hass.loop, host, port, reconnect=True
            )
        except socket.gaierror:
            errors["base"] = "unknown"
        except ConnectionRefusedError:
            errors["base"] = "cannot_connect"
        finally:
            if "client" in locals():
                del client

        await self.async_set_unique_id("Snapcast")
        self._abort_if_unique_id_configured()

        if errors:
            _LOGGER.error(
                "Could not connect to a Snapcast Server at the provided address"
            )
            _LOGGER.error(f"Error: {errors['base']}")
            return _show_form(errors=errors)

        return self.async_create_entry(
            title=f"{host}:{port}",
            data=user_input,
        )
