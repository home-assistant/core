"""The Fluss+ integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .coordinator import FlussDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON]


type FlussConfigEntry = ConfigEntry[FlussDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
) -> bool:
    """Set up Fluss+ from a config entry."""
    coordinator = FlussDataUpdateCoordinator(hass, entry, entry.data[CONF_API_KEY])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FlussConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
