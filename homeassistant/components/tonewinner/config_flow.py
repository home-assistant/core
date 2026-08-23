"""Tonewinner AT-500 configuration flow."""

from typing import Any, override

from tonewinner_rs232 import TonewinnerReceiver
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow as ConfigEntryFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import SerialPortSelector

from .const import (
    CONF_BAUD_RATE,
    CONF_SERIAL_PORT,
    CONF_SOURCE_MAPPINGS,
    DEFAULT_BAUD_RATE,
    DOMAIN,
)
from .media_player import INPUT_SOURCES

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): SerialPortSelector(),
        vol.Required(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE): cv.positive_int,
    }
)


class TonewinnerConfigFlow(ConfigEntryFlow, domain=DOMAIN):
    """Handle the initial step of the configuration flow."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial step of configuration flow."""
        errors = {}
        if user_input is not None:
            try:
                receiver = TonewinnerReceiver(
                    user_input[CONF_SERIAL_PORT],
                    baudrate=user_input[CONF_BAUD_RATE],
                )
                await receiver.connect()
                await receiver.disconnect()
            except OSError:
                errors["base"] = "cannot_connect"
            if not errors:
                await self.async_set_unique_id(user_input[CONF_SERIAL_PORT])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Tonewinner AT-500", data=user_input, options={}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the serial port connection."""
        errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                receiver = TonewinnerReceiver(
                    user_input[CONF_SERIAL_PORT],
                    baudrate=user_input[CONF_BAUD_RATE],
                )
                await receiver.connect()
                await receiver.disconnect()
            except OSError:
                errors["base"] = "cannot_connect"
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, self._get_reconfigure_entry().data
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return TonewinnerOptionsFlow(config_entry)


class TonewinnerOptionsFlow(OptionsFlow):
    """Handle options flow for Tonewinner."""

    _config_entry: ConfigEntry

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            source_mappings = {}
            for source_name, source_code in INPUT_SOURCES.items():
                enabled_key = f"{source_code}_enabled"
                name_key = f"{source_code}_name"

                if enabled_key in user_input:
                    source_mappings[source_code] = {
                        "enabled": user_input[enabled_key],
                        "name": user_input.get(name_key, source_name),
                    }

            return self.async_create_entry(
                title="", data={CONF_SOURCE_MAPPINGS: source_mappings}
            )

        current_mappings = self._config_entry.options.get(CONF_SOURCE_MAPPINGS, {})

        schema: dict[vol.Marker, Any] = {}
        for source_name, source_code in INPUT_SOURCES.items():
            current_mapping = current_mappings.get(source_code, {})
            enabled = current_mapping.get("enabled", True)
            custom_name = current_mapping.get("name", source_name)

            schema[vol.Optional(f"{source_code}_enabled", default=enabled)] = cv.boolean
            schema[vol.Optional(f"{source_code}_name", default=custom_name)] = cv.string

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )
