"""Config flow for the Grid Connect integration in Home Assistant.

This module handles the UI configuration flow, allowing users to
set up and manage their integration settings.
"""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GridConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Grid Connect."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}  # Initialize errors here

        if user_input is not None:
            # Check if the device is already configured
            existing_entries = self.hass.config_entries.async_entries(DOMAIN)
            for entry in existing_entries:
                if (
                    entry.data[CONF_HOST] == user_input[CONF_HOST]
                ):  # Adjust as necessary
                    return self.async_abort(reason="already_configured")

            try:
                # Assume validate_input is a function that validates the input
                await self._validate_input(user_input)
                return self.async_create_entry(title="Grid Connect", data=user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("host"): str,
                }
            ),
            errors=errors,
        )

    async def _validate_input(self, data):
        """Validate the user input allows us to connect."""
        # Implement your validation logic here

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow handler for Grid Connect."""
        return GridConnectOptionsFlowHandler(config_entry)


class GridConnectOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Grid Connect."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "option1", default=self.config_entry.options.get("option1", "")
                    ): str
                }
            ),
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
