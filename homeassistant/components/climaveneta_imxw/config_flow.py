"""Support for the Mitsubishi-Climaveneta iMXW fancoil series."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.modbus import get_hub
from homeassistant.const import CONF_NAME, CONF_SLAVE, DEVICE_DEFAULT_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_HUB, DEFAULT_MODBUS_HUB, DEFAULT_SERIAL_SLAVE_ID, DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Climaveneta_imxw."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step when user initializes a integration."""
        errors = {}
        if user_input is not None:
            try:
                get_hub(self.hass, user_input[CONF_HUB])
            except KeyError:
                errors["hub"] = "invalid_modbus_hub"

            if not errors:
                title_device = f"Climaveneta_IMXW {user_input[CONF_NAME]} at {user_input[CONF_HUB]}:{user_input[CONF_SLAVE]}"
                return self.async_create_entry(title=title_device, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HUB, default=str(DEFAULT_MODBUS_HUB)): str,
                vol.Required(CONF_SLAVE, default=int(DEFAULT_SERIAL_SLAVE_ID)): vol.All(
                    int, vol.Range(min=0, max=255)
                ),
                vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
