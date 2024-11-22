"""Config flow for Imeon integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ImeonInverterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow for Imeon Inverters."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step for creating a new configuration entry."""
        schema = vol.Schema(
            {
                vol.Required("inverter"): str,
                vol.Required(CONF_ADDRESS): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=schema)

        # Check if entry already exists
        existing_entry = self._find_existing_entry(
            user_input[CONF_ADDRESS], user_input["inverter"]
        )

        if existing_entry:
            return self.async_abort(reason="already_configured")

        data = {
            "address": user_input["address"],
            "username": user_input["username"],
            "password": user_input["password"],
        }

        return self.async_create_entry(title=user_input["inverter"], data=data)

    def _find_existing_entry(
        self, address: str, inverter_name: str
    ) -> config_entries.ConfigEntry | None:
        """Check if an entry with the same address or inverter name already exists."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data[CONF_ADDRESS] == address or entry.title == inverter_name:
                return entry
        return None
