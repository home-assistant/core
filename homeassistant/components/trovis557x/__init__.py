"""The Samson Trovis 557x integration.

Trovis is a Modbus device. This integration does not own its connection: it
borrows a ``ModbusUnit`` from a ``modbus_connection`` config entry (chosen in the
config flow) and hands it to the ``trovis_modbus`` library. The
``modbus_connection`` entry owns the connection lifecycle and reloads.
"""

from trovis_modbus import Trovis557x

from homeassistant.components.modbus_connection import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_CONNECTION, CONF_UNIT_ID
from .coordinator import TrovisConfigEntry, TrovisCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.WATER_HEATER,
]


async def async_setup_entry(hass: HomeAssistant, entry: TrovisConfigEntry) -> bool:
    """Set up Trovis 557x from a config entry.

    ``async_get_unit`` raises ``ConnectionNotReady`` (a ``ConfigEntryNotReady``)
    if the shared connection is missing or not loaded; letting it propagate gives
    Home Assistant's setup retry.
    """
    unit = async_get_unit(
        hass, entry.data[CONF_CONNECTION], int(entry.data[CONF_UNIT_ID])
    )
    device = Trovis557x(unit)
    coordinator = TrovisCoordinator(hass, entry, device)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TrovisConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
