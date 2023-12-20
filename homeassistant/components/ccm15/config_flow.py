"""Config flow for Midea ccm15 AC Controller integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .climate import CCM15Coordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=80): cv.port,
    }
)


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], existing_hosts: list[str]
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    host: str = data[CONF_HOST]
    for existing_host in existing_hosts:
        if existing_host == host:
            raise DuplicateEntry

    hub = CCM15Coordinator(hass, host, data[CONF_PORT])
    if not await hub.async_test_connection():
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {
        CONF_HOST: data[CONF_HOST],
        CONF_PORT: data[CONF_PORT],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Midea ccm15 AC Controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                existing_hosts = [
                    entry.data[CONF_HOST] for entry in self._async_current_entries()
                ]
                info = await validate_input(self.hass, user_input, existing_hosts)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info[CONF_HOST], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class DuplicateEntry(HomeAssistantError):
    """Error to indicate an existing entry already exist."""
