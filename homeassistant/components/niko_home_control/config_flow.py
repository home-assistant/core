"""Config flow for the Niko home control integration."""

from __future__ import annotations

import ipaddress
from typing import Any

from nikohomecontrol import NikoHomeControlConnection
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DEFAULT_IP, DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .errors import CannotConnect, InvalidHost, InvalidPort


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, str | int]:
    """Validate the user input allows us to connect."""
    name = data[CONF_NAME]
    host = data[CONF_HOST]
    port = data[CONF_PORT]

    try:
        ipaddress.ip_address(host)
    except ValueError:
        raise InvalidHost from None

    if port < 0 or port > 65535:
        raise InvalidPort

    controller = NikoHomeControlConnection(host, port)

    if not controller:
        raise CannotConnect

    return {"name": name, "host": host, "port": port}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Niko Home Control."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self, import_info=None) -> None:
        """Initialize the config flow."""
        self._config: Any = {}
        self._entities: Any = {}
        self._import_info: Any = import_info

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        HOST = DEFAULT_IP
        if self._import_info is not None:
            if self._import_info["host"] is not None:
                HOST = self._import_info["host"]

        DATA_SCHEMA = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HOST, default=HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
            }
        )

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
                return self.async_create_entry(
                    title=DOMAIN,
                    data={
                        "config": self._config,
                        "options": user_input,
                        "entities": self._entities,
                    },
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "invalid_host"
            except InvalidPort:
                errors["port"] = "invalid_port"

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_info) -> ConfigFlowResult:
        """Import a config entry."""
        self._import_info = import_info
        return await self.async_step_user(None)
