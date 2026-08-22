"""Config flow for the Flexit integration."""

import logging
from typing import Any, override

from flexit_modbus import Flexit
from modbus_connection import ModbusConnection, ModbusError
from modbus_connection.pymodbus import connect_serial, connect_tcp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_SLAVE, CONF_TYPE
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SerialPortSelector,
    TextSelector,
)

from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_STOPBITS,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)

_LOGGER = logging.getLogger(__name__)

SLAVE_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(min=0, max=32, mode=NumberSelectorMode.BOX)),
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
        vol.Required(CONF_SLAVE): SLAVE_SELECTOR,
    }
)

STEP_SERIAL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialPortSelector(),
        vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.All(
            NumberSelector(NumberSelectorConfig(min=1, mode=NumberSelectorMode.BOX)),
            vol.Coerce(int),
        ),
        vol.Required(CONF_BYTESIZE, default=DEFAULT_BYTESIZE): vol.All(
            SelectSelector(SelectSelectorConfig(options=["7", "8"])),
            vol.Coerce(int),
        ),
        vol.Required(CONF_PARITY, default=DEFAULT_PARITY): SelectSelector(
            SelectSelectorConfig(options=["N", "E", "O"])
        ),
        vol.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS): vol.All(
            SelectSelector(SelectSelectorConfig(options=["1", "2"])),
            vol.Coerce(int),
        ),
        vol.Required(CONF_SLAVE): SLAVE_SELECTOR,
    }
)


async def _connect(data: dict[str, Any]) -> ModbusConnection:
    """Open a Modbus connection matching the given config entry data."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        return await connect_serial(
            data[CONF_DEVICE],
            baudrate=data[CONF_BAUDRATE],
            bytesize=data[CONF_BYTESIZE],
            parity=data[CONF_PARITY],
            stopbits=data[CONF_STOPBITS],
        )
    return await connect_tcp(data[CONF_HOST], port=data[CONF_PORT])


async def check_connection(data: dict[str, Any]) -> str | None:
    """Check we can open a connection and read from the Flexit unit."""
    try:
        connection = await _connect(data)
        try:
            await Flexit(connection.for_unit(data[CONF_SLAVE])).async_update()
        finally:
            await connection.close()
    except ModbusError:
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
            self._async_abort_entries_match(data)
            error = await check_connection(data)
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
            self._async_abort_entries_match(data)
            error = await check_connection(data)
            if error is not None:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    config_entry, data_updates=data
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, config_entry.data),
            errors=errors,
        )
