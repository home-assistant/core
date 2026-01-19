"""Tonewinner AT-500 configuration flow."""

import logging
from typing import Any

import serial
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow as ConfigEntryFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BAUD_RATE,
    CONF_SERIAL_PORT,
    CONF_SOURCE_MAPPINGS,
    DEFAULT_BAUD_RATE,
    DOMAIN,
)
from .media_player import INPUT_SOURCES

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
                errors["base"] = "cannot_connect"
            if not errors:
                _LOGGER.info("Creating config entry with data: %s", user_input)
                return self.async_create_entry(
                    title="Tonewinner AT-500", data=user_input, options={}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL_PORT, default="/dev/ttyUSB0"): cv.string,
                    vol.Required(
                        CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE
                    ): cv.positive_int,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return TonewinnerOptionsFlow(config_entry)


class TonewinnerOptionsFlow(OptionsFlow):
    """Handle options flow for Tonewinner."""

    _config_entry: ConfigEntry

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            _LOGGER.debug("Saving options: %s", user_input)

            # Update serial port settings in entry data
            new_data = dict(self._config_entry.data)
            if CONF_SERIAL_PORT in user_input:
                new_data[CONF_SERIAL_PORT] = user_input[CONF_SERIAL_PORT]
            if CONF_BAUD_RATE in user_input:
                new_data[CONF_BAUD_RATE] = user_input[CONF_BAUD_RATE]

            _LOGGER.debug("Updating entry data: %s", new_data)

            # Update the config entry with new data
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )

            # Transform form data into source_mappings structure
            source_mappings = {}
            for source_name, source_code in INPUT_SOURCES.items():
                enabled_key = f"{source_code}_enabled"
                name_key = f"{source_code}_name"

                if enabled_key in user_input:
                    source_mappings[source_code] = {
                        "enabled": user_input[enabled_key],
                        "name": user_input.get(name_key, source_name),
                    }
                    _LOGGER.debug(
                        "Source mapping: %s -> enabled=%s, name=%s",
                        source_code,
                        user_input[enabled_key],
                        user_input.get(name_key, source_name),
                    )

            _LOGGER.debug("Final source_mappings to save: %s", source_mappings)

            return self.async_create_entry(
                title="", data={CONF_SOURCE_MAPPINGS: source_mappings}
            )

        # Get current options
        current_mappings = self._config_entry.options.get(CONF_SOURCE_MAPPINGS, {})
        _LOGGER.debug(
            "Loading current source_mappings from options: %s", current_mappings
        )
        _LOGGER.debug("Full config entry options: %s", self._config_entry.options)

        # Build options schema as list to avoid mypy type issues
        schema_items: list[tuple[Any, Any]] = []

        # Add serial port configuration at the top
        schema_items.append(
            (
                vol.Optional(
                    CONF_SERIAL_PORT,
                    default=self._config_entry.data.get(
                        CONF_SERIAL_PORT, "/dev/ttyUSB0"
                    ),
                ),
                cv.string,
            )
        )
        schema_items.append(
            (
                vol.Optional(
                    CONF_BAUD_RATE,
                    default=self._config_entry.data.get(
                        CONF_BAUD_RATE, DEFAULT_BAUD_RATE
                    ),
                ),
                cv.positive_int,
            )
        )

        # Add source mappings
        for source_name, source_code in INPUT_SOURCES.items():
            # Default to enabled (True) and use source name as default custom name
            current_mapping = current_mappings.get(source_code, {})
            enabled = current_mapping.get("enabled", True)
            custom_name = current_mapping.get("name", source_name)

            _LOGGER.debug(
                "Source %s (%s): enabled=%s, custom_name=%s",
                source_name,
                source_code,
                enabled,
                custom_name,
            )

            schema_items.append(
                (vol.Optional(f"{source_code}_enabled", default=enabled), cv.boolean)
            )
            schema_items.append(
                (vol.Optional(f"{source_code}_name", default=custom_name), cv.string)
            )

        _LOGGER.debug("Options schema items: %s", schema_items)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(dict(schema_items)),
        )
