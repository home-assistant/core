"""Config flow for homecom integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from . import Hub
from .const import DOMAIN
from .exceptions import CannotConnect, InvalidAuth

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for homecom."""

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
        session = aiohttp_client.async_get_clientsession(self.hass)
        hub = Hub(
            self.hass,
            session,
            user_input["username"],
            user_input["password"],
        )
        try:
            await hub.authenticate()
        except InvalidAuth:
            errors["base"] = "invalid_auth"
            return self.async_show_form(step_id="auth", errors=errors)
        except CannotConnect:
            errors["base"] = "cannot_connect"
            return self.async_show_form(step_id="auth", errors=errors)

        return self.async_create_entry(title="auth", data=user_input)
