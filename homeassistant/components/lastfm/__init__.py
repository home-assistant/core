"""The lastfm component."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import LastFMConfigEntry, LastFMDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: LastFMConfigEntry) -> bool:
    """Set up lastfm from a config entry."""

    coordinator = LastFMDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LastFMConfigEntry) -> bool:
    """Unload lastfm config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
