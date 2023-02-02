"""Config flow for Imazu Wall Pad integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from wp_imazu.client import ImazuClient

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_PORT, DOMAIN
from .helper import format_host

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_validate_connection(host: str, port: int) -> dict[str, str]:
    """Validate if a connection to Wall Pad can be established."""
    errors = {}

    client = ImazuClient(host, port)
    if not await client.async_connect():
        errors["base"] = "cannot_connect"
    client.disconnect()

    return errors


class WallPadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Imazu Wall Pad."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]

        if errors := await async_validate_connection(host, port):
            return self.async_show_form(
                step_id="user",
                data_schema=CONFIG_SCHEMA,
                errors=errors,
            )
        host_formatted = format_host(host)
        await self.async_set_unique_id(host_formatted)
        return self.async_create_entry(title=host, data=user_input)
