"""The hifiberry integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pyhifiberry.audiocontrol2 import Audiocontrol2, Audiocontrol2Exception


from .const import DOMAIN, DATA_HIFIBERRY, DATA_INIT

PLATFORMS = ["media_player"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up hifiberry from a config entry."""

    api = Audiocontrol2(
        async_get_clientsession(hass),
        host=entry.data["host"],
        port=entry.data["port"],
        authtoken=entry.data["authtoken"],
    )

    try:
        meta = await api.metadata()
        volume = await api.volume()
    except Audiocontrol2Exception as error:
        raise ConfigEntryNotReady from error

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_HIFIBERRY: api,
        DATA_INIT: (meta, volume),
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
