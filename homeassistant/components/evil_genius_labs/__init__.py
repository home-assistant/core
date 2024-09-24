"""The Evil Genius Labs integration."""

from __future__ import annotations

import pyevilgenius

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .coordinator import EvilGeniusUpdateCoordinator

PLATFORMS = [Platform.LIGHT]

UPDATE_INTERVAL = 10


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Evil Genius Labs from a config entry."""
    coordinator = EvilGeniusUpdateCoordinator(
        hass,
        entry.title,
        pyevilgenius.EvilGeniusDevice(
            entry.data["host"], aiohttp_client.async_get_clientsession(hass)
        ),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
