"""The DD-WRT integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import DdWrtConfigEntry, DdWrtDataUpdateCoordinator

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: DdWrtConfigEntry) -> bool:
    """Set up DD-WRT from a config entry."""
    coordinator = DdWrtDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DdWrtConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
