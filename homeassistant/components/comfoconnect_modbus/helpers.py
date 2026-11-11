"""Helpers for the Zehnder ComfoConnect PRO integration."""

from collections.abc import Mapping
from typing import Any

from modbus_connection import ModbusSerialParams, ModbusTcpParams

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE

from .const import CONF_BAUDRATE, CONF_PARITY, PARITIES, TYPE_SERIAL


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        parity = PARITIES[data[CONF_PARITY]]
        return ModbusSerialParams(
            device=data[CONF_DEVICE],
            baudrate=data[CONF_BAUDRATE],
            parity=parity,
            # The gateway takes 2 stop bits without parity and 1 with it.
            stopbits=2 if parity == "N" else 1,
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
