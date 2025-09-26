"""The trafikverket_weatherstation component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import TVDataUpdateCoordinator

TVWeatherConfigEntry = ConfigEntry[TVDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TVWeatherConfigEntry) -> bool:
    """Set up Trafikverket Weatherstation from a config entry."""

    coordinator = TVDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TVWeatherConfigEntry) -> bool:
    """Unload Trafikverket Weatherstation config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
