"""Connection helpers for aerosmart."""

from collections.abc import Mapping
from typing import Any

from modbus_connection import ModbusSerialParams, ModbusTcpParams

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE

from .const import CONF_BAUDRATE, TYPE_SERIAL

_DEVICE_TYPE_NAMES = {
    4: "aerosmart s",
    5: "aerosmart m",
    6: "aerosmart l",
    7: "aerosmart xls",
    11: "aerosmart mono",
}


def format_device_type(device_type: int) -> str:
    """Return the product name for a device type code."""
    return _DEVICE_TYPE_NAMES.get(device_type, str(device_type))


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build Modbus connection parameters from config entry data."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE], baudrate=data[CONF_BAUDRATE]
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
