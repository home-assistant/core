"""Support for testing internet speed via Fast.com."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, PLATFORMS
from .coordinator import FastdotcomConfigEntry, FastdotcomDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: FastdotcomConfigEntry) -> bool:
    """Set up Fast.com from a config entry."""
    coordinator = FastdotcomDataUpdateCoordinator(hass, entry)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_finish_startup(hass: HomeAssistant) -> None:
        """Run after Home Assistant startup is complete."""
        await coordinator.async_refresh()

    async_at_started(hass, _async_finish_startup)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FastdotcomConfigEntry) -> bool:
    """Unload Fast.com config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
