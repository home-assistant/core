"""Config flow for TED integration."""
from __future__ import annotations

import logging
from typing import Any

import httpx
import tedpy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL = "serial"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TED."""

    VERSION = 1

    def __init__(self):
        """Initialize an TED flow."""
        self.ip_address = None
        self.name = None
        self.serial = None

    @callback
    def _async_generate_schema(self):
        """Generate schema."""
        schema = {}

        if self.ip_address:
            schema[vol.Required(CONF_HOST, default=self.ip_address)] = vol.In(
                [self.ip_address]
            )
        else:
            schema[vol.Required(CONF_HOST)] = str

        return vol.Schema(schema)

    async def async_step_import(self, import_config):
        """Handle a flow import."""
        self.ip_address = import_config[CONF_IP_ADDRESS]
        self.name = import_config[CONF_NAME]
        return await self.async_step_user(
            {
                CONF_HOST: import_config[CONF_IP_ADDRESS],
            }
        )

    @callback
    def _async_current_hosts(self):
        """Return a set of hosts."""
        return {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_HOST in entry.data
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            if user_input[CONF_HOST] in self._async_current_hosts():
                return self.async_abort(reason="already_configured")

            try:
                reader = await tedpy.createTED(
                    user_input[CONF_HOST], async_client=get_async_client(self.hass)
                )
                await reader.update()
                self.serial = reader.gateway_id
                await self.async_set_unique_id(self.serial)
            except httpx.HTTPError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data = user_input.copy()
                data[CONF_NAME] = f"TED {self.serial}"
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self._async_generate_schema(),
            errors=errors,
        )
