"""The National Grid US integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import NationalGridConfigEntry, NationalGridDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: NationalGridConfigEntry
) -> bool:
    """Set up National Grid US from a config entry."""
    coordinator = NationalGridDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NationalGridConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
