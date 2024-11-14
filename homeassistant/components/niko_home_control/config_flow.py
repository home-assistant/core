"""Config flow for the Niko home control integration."""

from __future__ import annotations

from typing import Any

from homeassistant.exceptions import ConfigEntryNotReady
from nikohomecontrol import NikoHomeControlConnection
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DEFAULT_IP, DEFAULT_PORT, DOMAIN
from .errors import CannotConnect


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, str | int]:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]

    controller = NikoHomeControlConnection(host, port)

    if not controller:
        raise ConfigEntryNotReady

    return {"host": host, "port": port}


class NikoHomeControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Niko Home Control."""

    VERSION = 1

    def __init__(self, import_info=None) -> None:
        """Initialize the config flow."""
        if import_info is not None:
          self._import_info: dict[str, str] = import_info

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        HOST = DEFAULT_IP
        if self._import_info is not None:
            if self._import_info["host"] is not None:
                HOST = self._import_info["host"]

        DATA_SCHEMA = vol.Schema(
            {
                vol.Required(CONF_HOST, default=HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
            }
        )

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except ConfigEntryNotReady :
                errors["base"] = "cannot_connect"


            return self.async_create_entry(
                title=DOMAIN,
                data=user_input,
            )

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_info) -> ConfigFlowResult:
        """Import a config entry."""
        self._import_info = import_info
        return await self.async_step_user(None)
