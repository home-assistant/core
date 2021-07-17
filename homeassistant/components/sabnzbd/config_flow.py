"""Adds config flow for SabNzbd."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
)
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DEFAULT_SSL, DOMAIN
from .errors import AuthenticationError
from .sab import get_client

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Optional(CONF_PATH): str,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
    }
)


class SABnzbdConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Sabnzbd config flow."""

    VERSION = 1

    async def _async_validate_input(self, user_input):
        """Validate the user input allows us to connect."""
        errors = {}
        try:
            await get_client(self.hass, user_input)

        except AuthenticationError:
            errors["base"] = "cannot_connect"

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:

            errors = await self._async_validate_input(user_input)

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )
