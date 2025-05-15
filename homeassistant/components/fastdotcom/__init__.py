"""Support for testing internet speed via Fast.com."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import FastdotcomConfigEntry, FastdotcomDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: FastdotcomConfigEntry) -> bool:
    """Set up Fast.com from a config entry."""
    coordinator = FastdotcomDataUpdateCoordinator(hass, entry)
    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hass.loop.create_task(coordinator.async_refresh())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FastdotcomConfigEntry) -> bool:
    """Unload Fast.com config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
