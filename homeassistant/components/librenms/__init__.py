"""The LibreNMS integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import LibrenmsConfigEntry, LibrenmsDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LibrenmsConfigEntry) -> bool:
    """Set up LibreNMS from a config entry."""

    coordinator = LibrenmsDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LibrenmsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
