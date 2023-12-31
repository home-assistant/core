"""The Govee Lights - Local API integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import GoveeLocalApiCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]
SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee Local API from a config entry."""

    coordinator: GoveeLocalApiCoordinator = GoveeLocalApiCoordinator(
        hass=hass, scan_interval=SCAN_INTERVAL, logger=_LOGGER
    )
    entry.async_on_unload(coordinator.clenaup)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await coordinator.start()

    await coordinator.async_config_entry_first_refresh()

    try:
        async with asyncio.timeout(delay=5):
            while not coordinator.devices:
                await asyncio.sleep(delay=1)
    except asyncio.TimeoutError:
        _LOGGER.debug("No devices found")

    hass.async_add_job(hass.config_entries.async_forward_entry_setups(entry, PLATFORMS))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
    return False
