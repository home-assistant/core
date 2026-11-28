"""Helpers shared by the config flow and the entry setup."""

from collections.abc import Mapping
from typing import Any

from modbus_connection import ModbusSerialParams, ModbusTcpParams

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE

from .const import CONF_BAUDRATE, CONF_UNIT_ID, TYPE_SERIAL


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build the Modbus link parameters from config entry data.

    On a serial link the gateway always uses 8 data bits, no parity and 2
    stop bits.
    """
    if data[CONF_TYPE] == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE],
            baudrate=data[CONF_BAUDRATE],
            bytesize=8,
            parity="N",
            stopbits=2,
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def link_match(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return the entry data that tells which gateway these link settings reach."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        return {CONF_DEVICE: data[CONF_DEVICE], CONF_UNIT_ID: data[CONF_UNIT_ID]}
    return {
        CONF_HOST: data[CONF_HOST],
        CONF_PORT: data[CONF_PORT],
        CONF_UNIT_ID: data[CONF_UNIT_ID],
    }
