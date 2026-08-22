"""Modbus connection helpers for the Flexit integration."""

from collections.abc import Mapping
from typing import Any, Literal, cast

from modbus_connection import ModbusSerialParams, ModbusTcpParams
from modbus_connection.pymodbus import ModbusConnection

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE

from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_PORT,
    TYPE_SERIAL,
)


def create_modbus_connection(data: Mapping[str, Any]) -> ModbusConnection:
    """Create an unopened Modbus connection from config entry data."""
    params: ModbusSerialParams | ModbusTcpParams
    if data[CONF_TYPE] == TYPE_SERIAL:
        params = ModbusSerialParams(
            device=data[CONF_DEVICE],
            baudrate=data[CONF_BAUDRATE],
            bytesize=cast(Literal[7, 8], data[CONF_BYTESIZE]),
            parity=cast(Literal["N", "E", "O"], data[CONF_PARITY]),
            stopbits=cast(Literal[1, 2], data[CONF_STOPBITS]),
        )
    else:
        params = ModbusTcpParams(
            host=data[CONF_HOST], port=data.get(CONF_PORT, DEFAULT_PORT)
        )
    return ModbusConnection(params)
