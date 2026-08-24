"""The Flexit component, for AC units with a CI66 Modbus adapter."""

from collections.abc import Mapping
from typing import Any, Literal, cast

from modbus_connection import ModbusSerialParams, ModbusTcpParams
from modbus_connection.pymodbus import ModbusConnection

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_UNIT,
    DEFAULT_PORT,
    TYPE_SERIAL,
)
from .coordinator import FlexitConfigEntry, FlexitDataCoordinator

_PLATFORMS: list[Platform] = [Platform.CLIMATE]


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


async def async_setup_entry(hass: HomeAssistant, entry: FlexitConfigEntry) -> bool:
    """Set up Flexit from a config entry."""
    connection = create_modbus_connection(entry.data)
    entry.async_on_unload(connection.close)

    coordinator = FlexitDataCoordinator(hass, entry, connection, entry.data[CONF_UNIT])

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: FlexitConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
