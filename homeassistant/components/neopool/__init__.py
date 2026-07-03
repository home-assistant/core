"""NeoPool integration for Home Assistant."""

from neopool_modbus import NeoPoolModbusClient

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import NeoPoolConfigEntry, NeoPoolCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> bool:
    """Set up the NeoPool integration from a config entry."""
    client = NeoPoolModbusClient(entry.data)
    coordinator = NeoPoolCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeoPoolConfigEntry) -> bool:
    """Unload a NeoPool config entry."""
    coordinator = entry.runtime_data
    await coordinator.client.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
