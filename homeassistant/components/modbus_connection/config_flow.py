"""Config flow for the Modbus Connection integration."""

from typing import Any, override

from modbus_connection import ModbusError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
)

from . import _async_open
from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_STOPBITS,
    DOMAIN,
)

STEP_MODBUS_TCP = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
    }
)

# SerialPortSelector lists local serial ports and network serial proxies.
STEP_SERIAL = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialPortSelector(),
        vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Required(CONF_PARITY, default=DEFAULT_PARITY): SelectSelector(
            SelectSelectorConfig(
                options=["N", "E", "O"],
                translation_key="parity",
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS): vol.In([1, 2]),
        vol.Required(CONF_BYTESIZE, default=DEFAULT_BYTESIZE): vol.In([7, 8]),
    }
)


class ModbusConnectionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Modbus Connection."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose the transport."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["modbus_tcp", "serial"],
        )

    async def async_step_modbus_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a Modbus TCP / RTU-over-TCP connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: CONNECTION_TCP, **user_input}
            self._abort_if_configured(data)
            if not (errors := await self._async_validate(data)):
                return self.async_create_entry(
                    title=f"{data[CONF_HOST]}:{data[CONF_PORT]}", data=data
                )
        return self.async_show_form(
            step_id="modbus_tcp", data_schema=STEP_MODBUS_TCP, errors=errors
        )

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a Modbus serial (RTU) connection, incl. network serial proxies."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: CONNECTION_SERIAL, **user_input}
            self._abort_if_configured(data)
            if not (errors := await self._async_validate(data)):
                return self.async_create_entry(title=data[CONF_DEVICE], data=data)
        return self.async_show_form(
            step_id="serial", data_schema=STEP_SERIAL, errors=errors
        )

    def _abort_if_configured(self, data: dict[str, Any]) -> None:
        """Abort if this exact link is already configured.

        A Modbus endpoint has no hardware identity to use as a unique ID, so we
        dedupe by connection parameters. We check *before* opening the
        connection: most Modbus devices reject a second client, so probing one
        that is already in use would fail.
        """
        for entry in self._async_current_entries(include_ignore=True):
            if entry.data[CONF_TYPE] != data[CONF_TYPE]:
                continue
            if data[CONF_TYPE] == CONNECTION_SERIAL:
                configured = entry.data[CONF_DEVICE] == data[CONF_DEVICE]
            else:
                configured = (
                    entry.data[CONF_HOST] == data[CONF_HOST]
                    and entry.data[CONF_PORT] == data[CONF_PORT]
                )
            if configured:
                raise AbortFlow("already_configured")

    async def _async_validate(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate by actually opening the connection; return form errors."""
        try:
            connection = await _async_open(data)
        except ModbusError:
            if data[CONF_TYPE] == CONNECTION_SERIAL:
                return {"base": "cannot_open_serial_port"}
            return {"base": "cannot_connect"}
        await connection.close()
        return {}
