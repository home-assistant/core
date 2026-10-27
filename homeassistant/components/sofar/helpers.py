"""Helpers for the Sofar integration."""

from collections.abc import Mapping
from typing import Any

from modbus_connection import ModbusSerialParams, ModbusTcpParams

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import CONF_BAUDRATE, DOMAIN, TYPE_SERIAL

STORAGE_VERSION = 1

type StoredEntries = list[tuple[int, str]]


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE], baudrate=data[CONF_BAUDRATE]
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def fault_log_store(hass: HomeAssistant, entry_id: str) -> Store[StoredEntries]:
    """Return the store of the newest log entry an entry has handled."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.fault_log")
