"""The Flexit component, for AC units with a CI66 Modbus adapter."""

from collections.abc import Mapping
from typing import Any

from modbus_connection import ModbusSerialParams, ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_BAUDRATE, CONF_UNIT, DEFAULT_PORT, TYPE_SERIAL
from .coordinator import FlexitConfigEntry, FlexitDataCoordinator

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CLIMATE]


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Create Modbus connection parameters from config entry data."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE],
            baudrate=data[CONF_BAUDRATE],
            bytesize=8,
            parity="E",
            stopbits=1,
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data.get(CONF_PORT, DEFAULT_PORT))


async def async_setup_entry(hass: HomeAssistant, entry: FlexitConfigEntry) -> bool:
    """Set up Flexit from a config entry."""
    unit = async_get_unit(
        hass, entry, create_modbus_params(entry.data), entry.data[CONF_UNIT]
    )
    coordinator = FlexitDataCoordinator(hass, entry, unit)

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
