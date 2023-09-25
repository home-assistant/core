"""Config flow for zcc integration."""
from __future__ import annotations

import logging
import socket
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, TIMEOUT, VERBOSITY, WATCHDOG

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=""): str,
        vol.Optional(CONF_PORT, default=5003): int,
        vol.Optional(TIMEOUT, default=3): int,
        vol.Optional(VERBOSITY, default=1): int,
        vol.Optional(WATCHDOG, default=1800): int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""

    if data[TIMEOUT] is None:
        data[TIMEOUT] = 3

    if data[VERBOSITY] is None:
        data[VERBOSITY] = 1

    if data[WATCHDOG] is None:
        data[WATCHDOG] = 1800

    if data[CONF_HOST] != "":
        try:
            socket.gethostbyname(data[CONF_HOST])
        except socket.herror as e:
            raise CannotConnect("%s is not a valid host" % data[CONF_HOST]) from e

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((data[CONF_HOST], int(data[CONF_PORT])))
        except Exception as e:
            raise CannotConnect(
                f"{data[CONF_HOST]} {data[CONF_PORT]} is not reachable"
            ) from e

    # Return info that you want to store in the config entry.
    return {
        "title": "ZIMI Controller",
        "host": data[CONF_HOST],
        "port": data[CONF_PORT],
        "timeout": data[TIMEOUT],
        "verbosity": data[VERBOSITY],
        "watchdog": data[WATCHDOG],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zcc."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
