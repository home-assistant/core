"""Owns ModbusConnection and coordinator; sofar-modbus does register work."""

import logging

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from sofar_modbus.modern.device import identify

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Set up Sofar Inverter Modbus from a config entry."""
    serial = entry.unique_id
    assert serial is not None
    if not identify(serial)[0]:
        raise ConfigEntryError(f"Unrecognized Sofar inverter model for {entry.title}")

    connection = ModbusConnection(
        ModbusTcpParams(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
        )
    )
    entry.async_on_unload(connection.close)

    coordinator = SofarDataUpdateCoordinator(hass, entry, connection)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
