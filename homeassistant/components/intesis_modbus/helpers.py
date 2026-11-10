"""Helpers shared by the config flow and the entry setup."""

from collections.abc import Mapping
from typing import Any

from modbus_connection import ModbusSerialParams

from homeassistant.const import CONF_DEVICE

from .const import CONF_BAUDRATE


def create_modbus_params(data: Mapping[str, Any]) -> ModbusSerialParams:
    """Build the serial link parameters the gateway always uses: 8N2."""
    return ModbusSerialParams(
        device=data[CONF_DEVICE],
        baudrate=data[CONF_BAUDRATE],
        bytesize=8,
        parity="N",
        stopbits=2,
    )
