"""Support for Open-Meteo."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import OpenMeteoConfigEntry, OpenMeteoDataUpdateCoordinator

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: OpenMeteoConfigEntry) -> bool:
    """Set up Open-Meteo from a config entry."""

    coordinator = OpenMeteoDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenMeteoConfigEntry) -> bool:
    """Unload Open-Meteo config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
