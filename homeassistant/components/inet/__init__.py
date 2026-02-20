"""The iNet Radio integration."""

from __future__ import annotations

import logging

from inet_control import RadioManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

type INetConfigEntry = ConfigEntry[RadioManager]


async def _async_get_manager(hass: HomeAssistant) -> RadioManager:
    """Get or create the shared RadioManager instance."""
    if DOMAIN not in hass.data:
        manager = RadioManager()
        await manager.start()
        hass.data[DOMAIN] = {"manager": manager, "entry_count": 0}
    hass.data[DOMAIN]["entry_count"] += 1
    return hass.data[DOMAIN]["manager"]


async def async_setup_entry(hass: HomeAssistant, entry: INetConfigEntry) -> bool:
    """Set up iNet Radio from a config entry."""
    manager = await _async_get_manager(hass)
    host = entry.data[CONF_HOST]

    try:
        await manager.connect(host, timeout=5.0)
    except (TimeoutError, OSError) as err:
        hass.data[DOMAIN]["entry_count"] -= 1
        if hass.data[DOMAIN]["entry_count"] <= 0:
            await manager.stop()
            hass.data.pop(DOMAIN, None)
        raise ConfigEntryNotReady(f"Cannot connect to radio at {host}") from err

    entry.runtime_data = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: INetConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and DOMAIN in hass.data:
        hass.data[DOMAIN]["entry_count"] -= 1
        if hass.data[DOMAIN]["entry_count"] <= 0:
            manager: RadioManager = hass.data[DOMAIN]["manager"]
            await manager.stop()
            hass.data.pop(DOMAIN, None)
    return unload_ok
