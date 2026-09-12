"""The Hot Spring integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import HotSpringConfigEntry, HotSpringDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: HotSpringConfigEntry) -> bool:
    """Set up Hot Spring from a config entry."""
    coordinator = HotSpringDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HotSpringConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
