"""Build a modbus_connection ModbusConnection from a config entry.

TCP only for now. Constructing a connection performs no I/O; the first
request made against a unit connects on demand.
"""

from collections.abc import Mapping
from typing import Any

from modbus_connection import ModbusConnection as _Base, ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection

from homeassistant.const import CONF_HOST, CONF_PORT

from .const import CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR, DEFAULT_PORT


def build_connection(data: Mapping[str, Any]) -> _Base:
    """Build the connection for a config entry's data (TCP).

    ``Mapping``, not ``dict``: a config entry's own ``.data`` is a read-only
    ``MappingProxyType``, and this only ever reads from it.
    """
    return ModbusConnection(
        ModbusTcpParams(
            host=data[CONF_HOST],
            port=data.get(CONF_PORT, DEFAULT_PORT),
        )
    )


def unit_id(data: Mapping[str, Any]) -> int:
    """Return the configured Modbus unit/slave ID for a config entry's data."""
    return int(data.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR))
