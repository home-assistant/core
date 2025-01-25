"""Snapcast config flow."""

from __future__ import annotations

import logging
import socket

import snapcast.control
from snapcast.control.server import CONTROL_PORT
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import CONF_CREATE_GROUP_ENTITIES, DEFAULT_TITLE, DOMAIN

_LOGGER = logging.getLogger(__name__)

SNAPCAST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=CONTROL_PORT): int,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_CREATE_GROUP_ENTITIES,
            default=False,
        ): cv.boolean,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SnapcastOptionsFlow:
        """Return the options flow."""
        return SnapcastOptionsFlow()


class SnapcastOptionsFlow(OptionsFlow):
    """Snapcast options flow."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Handle the first step of options flow."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
