"""Tonewinner AT-500 configuration flow."""

import logging

import serial
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow as ConfigEntryFlow, ConfigFlowResult

from .const import CONF_BAUD_RATE, CONF_SERIAL_PORT, DEFAULT_BAUD_RATE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TonewinnerConfigFlow(ConfigEntryFlow, domain=DOMAIN):
    """Handle the initial step of the configuration flow."""

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle initial step of configuration flow."""
        _LOGGER.debug("Config flow step_user called")
        errors = {}
        if user_input is not None:
            _LOGGER.debug("User input received: %s", user_input)
            # Test the port briefly
            try:
                _LOGGER.debug(
                    "Testing serial port: %s at %d baud",
                    user_input[CONF_SERIAL_PORT],
                    user_input[CONF_BAUD_RATE],
                )
                s = serial.Serial(
                    user_input[CONF_SERIAL_PORT], user_input[CONF_BAUD_RATE], timeout=1
                )
                s.close()
                _LOGGER.debug("Serial port test successful")
            except (serial.SerialException, OSError) as e:
                _LOGGER.error("Serial port test failed: %s", e)
                errors["base"] = f"Cannot open port: {e}"
            if not errors:
                _LOGGER.info("Creating config entry with data: %s", user_input)
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
