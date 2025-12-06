"""Tonewinner AT-500 configuration flow."""

import serial
import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_BAUD_RATE, CONF_SERIAL_PORT, DEFAULT_BAUD_RATE, DOMAIN


class TonewinnerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial step of the configuration flow."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step of the configuration flow."""
        errors = {}
        if user_input is not None:
            # Test the port briefly
            try:
                s = serial.Serial(
                    user_input[CONF_SERIAL_PORT], user_input[CONF_BAUD_RATE], timeout=1
                )
                s.close()
            except Exception as e:
                errors["base"] = f"Cannot open port: {e}"
            if not errors:
                return self.async_create_entry(
                    title="Tonewinner AT-500", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL_PORT, default="/dev/ttyUSB0"): str,
                    vol.Required(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE): int,
                }
            ),
            errors=errors,
        )
