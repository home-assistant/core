"""The Swisscom Internet-Box integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SwisscomConfigEntry, SwisscomDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: SwisscomConfigEntry) -> None:
    """Set up Swisscom Internet-Box from a config entry."""
    coordinator = SwisscomDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: SwisscomConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
