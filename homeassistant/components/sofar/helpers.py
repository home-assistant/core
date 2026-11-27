"""Helpers for the Sofar integration."""

from collections.abc import Mapping
from enum import IntEnum
from typing import Any

from modbus_connection import ModbusSerialParams, ModbusTcpParams

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE

from .const import CONF_BAUDRATE, TYPE_SERIAL


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE], baudrate=data[CONF_BAUDRATE]
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def option_slug(member: IntEnum) -> str:
    """Return the option slug of a device enum member."""
    return member.name.lower()


def enum_options(enum_type: type[IntEnum]) -> list[str]:
    """Return the option slugs of a device enum."""
    return [option_slug(member) for member in enum_type]


def enum_member[E: IntEnum](enum_type: type[E], option: str) -> E:
    """Return the device enum member an option slug names."""
    return enum_type[option.upper()]
