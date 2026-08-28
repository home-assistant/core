"""Helpers for the SolarEdge Modbus integration."""

from collections.abc import Mapping
from typing import Any

from modbus_connection import ModbusTcpParams

from homeassistant.const import CONF_HOST, CONF_PORT


def create_modbus_params(data: Mapping[str, Any]) -> ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
