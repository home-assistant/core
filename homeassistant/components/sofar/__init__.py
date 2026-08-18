"""Sofar Inverter Modbus — owns the ModbusConnection and coordinator; sofar-modbus is the HA-free device library doing the register work.

Only the switch platform is wired up so far — added to Core one platform per PR.
"""

import logging

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Set up Sofar Inverter Modbus from a config entry."""
    connection = ModbusConnection(
        ModbusTcpParams(
            host=entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
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
