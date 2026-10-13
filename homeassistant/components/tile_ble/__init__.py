"""The Tile BLE integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import TileBleConfigEntry, TileBleCoordinator

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: TileBleConfigEntry) -> bool:
    """Set up Tile BLE from a config entry."""
    assert entry.unique_id is not None
    coordinator = TileBleCoordinator(hass, entry.unique_id)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TileBleConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
