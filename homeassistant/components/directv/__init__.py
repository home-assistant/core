"""The DirecTV integration."""

from __future__ import annotations

from datetime import timedelta

from directv import DIRECTV, DIRECTVError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.REMOTE]
SCAN_INTERVAL = timedelta(seconds=30)


type DirecTVConfigEntry = ConfigEntry[DIRECTV]


async def async_setup_entry(hass: HomeAssistant, entry: DirecTVConfigEntry) -> bool:
    """Set up DirecTV from a config entry."""
    dtv = DIRECTV(entry.data[CONF_HOST], session=async_get_clientsession(hass))

    try:
        await dtv.update()
    except DIRECTVError as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = dtv

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DirecTVConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
