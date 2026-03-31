"""The CentriConnect/MyPropane API integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import CentriConnectConfigEntry, CentriConnectCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: CentriConnectConfigEntry
) -> bool:
    """Set up CentriConnect/MyPropane API from a config entry."""
    coordinator = CentriConnectCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CentriConnectConfigEntry
) -> bool:
    """Unload CentriConnect/MyPropane API integration platforms and coordinator."""
    _LOGGER.info("Unloading CentriConnect/MyPropane API integration")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
