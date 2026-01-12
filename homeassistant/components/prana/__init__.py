"""Home Assistant Prana integration entry point.

Sets up the update coordinator and forwards platform setups.
"""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import PranaConfigEntry, PranaCoordinator

_LOGGER = logging.getLogger(__name__)

# Keep platforms sorted alphabetically to satisfy lint rule
PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: PranaConfigEntry) -> bool:
    """Set up Prana from a config entry."""

    coordinator = PranaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PranaConfigEntry) -> bool:
    """Unload Prana integration platforms and coordinator."""
    _LOGGER.info("Unloading Prana integration")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
