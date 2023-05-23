"""Config flow for myStrom integration."""
from __future__ import annotations

import ipaddress
import logging
import re
from typing import Any

import pymystrom
from pymystrom.exceptions import MyStromConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version == (4 or 6):
            return True
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(x and not disallowed.search(x) for x in host.split("."))


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    if not host_valid(data[CONF_HOST]):
        raise CannotConnect()
    try:
        info = await pymystrom.get_device_info(data[CONF_HOST])
    except MyStromConnectionError as error:
        raise CannotConnect() from error

    return {"mac": info.get("mac")}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for myStrom."""

    VERSION = 1

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle import from config."""
        return await self.async_step_user(import_config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info["mac"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["mac"], data=user_input)

        schema = self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
