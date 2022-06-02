"""Config flow for Radio Thermostat integration."""
from __future__ import annotations

import logging
from socket import timeout
from typing import Any

from radiotherm.validate import RadiothermTstatError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .data import async_get_name_from_host

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


async def validate_connection(hass: HomeAssistant, host: str) -> str:
    """Validate the connection."""
    try:
        name = await async_get_name_from_host(hass, host)
    except (timeout, RadiothermTstatError) as ex:
        raise CannotConnect from ex
    return name


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Radio Thermostat."""

    VERSION = 1

    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Import from yaml."""
        try:
            name = await validate_connection(self.hass, import_info[CONF_HOST])
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        return self.async_create_entry(title=name, data=import_info)

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
            name = await validate_connection(self.hass, user_input[CONF_HOST])
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=name, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
