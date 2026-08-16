"""Config flow — TCP only for Phase 1.

Probes the device to get its serial number for the unique_id.
"""

import logging
from typing import Any, override

from modbus_connection import ModbusError
from sofar_modbus.modern.device import SofarInverter
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .connection import build_connection, unit_id
from .const import (
    CONF_MODBUS_ADDR,
    CONF_READ_EPS,
    DEFAULT_MODBUS_ADDR,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_MODBUS_ADDR, default=DEFAULT_MODBUS_ADDR): int,
        vol.Optional(CONF_READ_EPS, default=False): bool,
    }
)


class SofarUnrecognizedError(Exception):
    """The device answered, but its serial number matched no known Sofar model."""

    def __init__(self, serial: str) -> None:
        """Initialize the error with the offending serial number."""
        super().__init__(f"unrecognized Sofar inverter, serial number: {serial!r}")
        self.serial = serial


async def _async_probe(data: dict[str, Any]) -> tuple[str, str | None]:
    """Return (serial, model), or raise ModbusError / SofarUnrecognizedError."""
    connection = build_connection(data)
    try:
        device = SofarInverter(
            connection.for_unit(unit_id(data)), read_eps=data.get(CONF_READ_EPS, False)
        )
        await device.async_setup()
        if not device.inverter_type:
            raise SofarUnrecognizedError(device.serial_number or "")
    finally:
        await connection.close()
    return device.serial_number or "", device.model


class SofarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Sofar Modbus config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial connection step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                serial, model = await _async_probe(user_input)
            except ModbusError:
                errors["base"] = "cannot_connect"
            except SofarUnrecognizedError:
                errors["base"] = "unrecognized_inverter"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=model or DEFAULT_NAME, data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the inverter connection."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            reconfig_data = {**entry.data, **user_input}
            try:
                serial, _ = await _async_probe(reconfig_data)
            except ModbusError:
                errors["base"] = "cannot_connect"
            except SofarUnrecognizedError:
                errors["base"] = "unrecognized_inverter"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_mismatch(reason="different_serial")
                return self.async_update_reload_and_abort(entry, data=reconfig_data)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST)): str,
                vol.Required(
                    CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)
                ): int,
                vol.Optional(
                    CONF_MODBUS_ADDR,
                    default=entry.data.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR),
                ): int,
                vol.Optional(
                    CONF_READ_EPS, default=entry.data.get(CONF_READ_EPS, False)
                ): bool,
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )
