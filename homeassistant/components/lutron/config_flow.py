"""Config flow to configure the Lutron integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN


class LutronConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """User prompt for Main Repeater configuration information."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """First step in the config flow."""
        errors = {}

        if user_input is not None:
            # Validate user input
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)
            ip_address = user_input.get(CONF_HOST)

            # Perform any validation here
            if not username or not password or not ip_address:
                errors["base"] = "missing_fields"
            else:
                # Check if a configuration entry with the same unique ID already exists
                existing_entries = self.hass.config_entries.async_entries(
                    DOMAIN
                )
                for entry in existing_entries:
                    if entry.data[CONF_HOST] == ip_address:
                        errors["base"] = "already_configured"

            if not errors:
                await self.async_set_unique_id(ip_address.replace(".", "_"))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Lutron Integration", data=user_input
                )

            return self.async_abort(reason="Errors Found in Configuration")

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input) -> FlowResult:
        """Handle import."""
        return await self.async_step_user(user_input)
