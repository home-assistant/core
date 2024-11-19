"""Config flow for Imeon integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN
from .coordinator import InverterCoordinator

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow for Imeon Inverters."""

    VERSION = 4

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step for creating a new configuration entry."""
        schema = vol.Schema(
            {
                vol.Required("inverter"): str,
                vol.Required("address"): str,
                vol.Required("username"): str,
                vol.Required("password"): str,
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=schema)

        data = {
            "address": user_input["address"],
            "username": user_input["username"],
            "password": user_input["password"],
        }

        return self.async_create_entry(title=user_input["inverter"], data=data)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the options flow for updating existing configurations."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow handler."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Provide a form to update the configuration entry."""
        if user_input is not None:
            HUB = InverterCoordinator.get_from_id(self._config_entry.entry_id)
            HUB.update(user_input)

            # Update config entry
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=user_input
            )

            return self.async_create_entry(
                title=self.config_entry.title, data=user_input
            )

        # Define the schema with default values
        schema = vol.Schema(
            {
                vol.Required(
                    "address", default=self._config_entry.data.get("address", "")
                ): str,
                vol.Required(
                    "username", default=self._config_entry.data.get("username", "")
                ): str,
                vol.Required(
                    "password", default=self._config_entry.data.get("password", "")
                ): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
