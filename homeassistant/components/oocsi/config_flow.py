"""Config flow for Oocsi for HomeAssistant integration."""
from __future__ import annotations

import logging

from oocsi import OOCSI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

# from homeassistant.core import Config, HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

# import socket
from typing import Any


# import homeassistant.helpers.config_validation as cv


"Import everything that is necessary"

# RANDOMISED = petname
_LOGGER = logging.getLogger(__name__)

PLATFORMS = "prototype"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4444


# TODO adjust the data schema to the data that you need
USER_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Oocsi for HomeAssistant."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if user_input is None:
            return self._async_show_form_popup()

        if user_input is not None:
            try:
                await self._connect_to_oocsi(user_input)
            except:
                return self._async_show_form_popup({"base": "cannot find oocsi"})
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: self.name,
                    CONF_HOST: self.host,
                    CONF_PORT: self.port,
                },
            )

    #    return self.async_show_form(step_id="user", data_schema=USER_CONFIG_SCHEMA, errors=errors)

    def _async_show_form_popup(
        self, errors: dict[str, str] | None = None
    ) -> FlowResult:
        return self.async_show_form(
            step_id="user", data_schema=USER_CONFIG_SCHEMA, errors=errors
        )

    async def _connect_to_oocsi(self, user_input):
        self.name = user_input[CONF_NAME]
        self.host = user_input[CONF_HOST]
        self.port = user_input[CONF_PORT]
        oocsiconnect = OOCSI(self.name, self.host, self.port)
        print(oocsiconnect.handle)
        await oocsiconnect.send("Bob", {"color": 120})


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
