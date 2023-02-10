"""Config flow for V2C integration."""
from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


def host_validate(host):
    """Return if the hostname/ip address is valid."""
    try:
        ip = ipaddress.ip_address(host)
        if ip.version == 4 or ip.version == 6:
            # Try to establish a socket connection to the host
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((str(ip), 502))
            if result == 0:
                return True
            else:
                return False
        else:
            return False
    except ValueError:
        _LOGGER.error("Error, %s is not a valid hostname/ip address", host)
        return False


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flow handler for the Example integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.data = {
            CONF_HOST: vol.UNDEFINED,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the configuration flow."""
        errors = {}
        id_entity = "trydan"
        host = user_input.get(CONF_HOST)
        if host:
            self.data[CONF_HOST] = host
            validation = host_validate(host)
            if validation is None:
                errors["base"] = "invalid_host"
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors=errors,
                )

            if validation is False:
                return self.async_abort(reason="host_error")

            await self.async_set_unique_id(id_entity, raise_on_progress=False)
            self._abort_if_unique_id_configured(updates=dict(self.data))

            return self.async_create_entry(title=self.data[CONF_HOST], data=self.data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, user_input) -> FlowResult:
        """Handle import."""
        return await self.async_step_user(user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
