"""Config flow for the Flexit integration."""

import logging
from typing import Any, override

from flexit_modbus import Flexit
from modbus_connection import ModbusError
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
    TextSelector,
)

from . import create_modbus_params
from .const import (
    CONF_BAUDRATE,
    CONF_UNIT,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)

_LOGGER = logging.getLogger(__name__)

UNIT_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(min=1, max=247, mode=NumberSelectorMode.BOX)),
    vol.Coerce(int),
)

STEP_TCP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            NumberSelector(
                NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
            ),
            vol.Coerce(int),
        ),
        vol.Required(CONF_UNIT): UNIT_SELECTOR,
    }
)

STEP_SERIAL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialPortSelector(),
        vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.All(
            NumberSelector(NumberSelectorConfig(min=1, mode=NumberSelectorMode.BOX)),
            vol.Coerce(int),
        ),
        vol.Required(CONF_UNIT): UNIT_SELECTOR,
    }
)


async def check_connection(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    """Check we can open a connection and read from the Flexit unit."""
    try:
        async with async_get_temporary_unit(
            hass, create_modbus_params(data), data[CONF_UNIT]
        ) as unit:
            await Flexit(unit).async_update()
    except HomeAssistantError, ModbusError:
        _LOGGER.debug("Cannot connect to Flexit device", exc_info=True)
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return "unknown"
    return None


class FlexitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flexit."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose between a network and a serial connection."""
        return self.async_show_menu(step_id="user", menu_options=["tcp", "serial"])

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the TCP connection step."""
        return await self._async_step_connection(
            TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input
        )

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the serial (RTU) connection step."""
        return await self._async_step_connection(
            TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_connection(
        self,
        connection_type: str,
        schema: vol.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Handle a connection-type-specific step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}
            if connection_type == TYPE_TCP:
                data[CONF_HOST] = data[CONF_HOST].lower()
            self._async_abort_entries_match(data)
            error = await check_connection(self.hass, data)
            if error is not None:
                errors["base"] = error
            else:
                return self.async_create_entry(title="Flexit", data=data)

        return self.async_show_form(
            step_id=connection_type, data_schema=schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        config_entry = self._get_reconfigure_entry()
        connection_type = config_entry.data[CONF_TYPE]
        schema = (
            STEP_SERIAL_DATA_SCHEMA
            if connection_type == TYPE_SERIAL
            else STEP_TCP_DATA_SCHEMA
        )

        errors: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}
            if connection_type == TYPE_TCP:
                data[CONF_HOST] = data[CONF_HOST].lower()
            self._async_abort_entries_match(data)

            entry_was_loaded = config_entry.state is ConfigEntryState.LOADED
            if entry_was_loaded and not await self.hass.config_entries.async_unload(
                config_entry.entry_id
            ):
                errors["base"] = "unknown"
            else:
                error = await check_connection(self.hass, data)
                if error is not None:
                    errors["base"] = error
                    if entry_was_loaded:
                        await self.hass.config_entries.async_setup(
                            config_entry.entry_id
                        )
                else:
                    return self.async_update_reload_and_abort(
                        config_entry, data_updates=data
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, config_entry.data),
            errors=errors,
        )
