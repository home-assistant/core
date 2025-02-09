"""The Epion integration."""

from __future__ import annotations

from epion import Epion

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .coordinator import EpionConfigEntry, EpionCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EpionConfigEntry) -> bool:
    """Set up the Epion coordinator from a config entry."""
    api = Epion(entry.data[CONF_API_KEY])
    coordinator = EpionCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EpionConfigEntry) -> bool:
    """Unload Epion config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
