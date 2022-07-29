"""Config flow for Satel Integra."""
from __future__ import annotations

import logging
from typing import Any

from satel_integra.satel_integra import AsyncSatel
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import CONF_DEVICE_CODE, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__package__)


class SatelFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Satel Integra config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            valid = await self.test_connection(
                user_input[CONF_HOST], user_input.get(CONF_PORT, DEFAULT_PORT)
            )

            if valid:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

            errors["base"] = "cannot_connect"

        data_schema = {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_DEVICE_CODE): cv.string,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a config entry."""

        user_input = {
            CONF_HOST: config[CONF_HOST],
            CONF_PORT: config.get(CONF_PORT, DEFAULT_PORT),
            CONF_DEVICE_CODE: config.get(CONF_DEVICE_CODE),
        }
        return await self.async_step_user(user_input)

    async def test_connection(self, host, port) -> bool:
        """Test a connection to the Satel alarm."""
        controller = AsyncSatel(host, port, self.hass.loop)

        result = await controller.connect()

        # Make sure we close the connection again
        controller.close()

        return result
