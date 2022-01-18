"""The Frontier Silicon NEW integration."""
from __future__ import annotations

from afsapi import AFSAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PIN, CONF_USE_SESSION, CONF_WEBFSAPI_URL, DOMAIN

PLATFORMS: list[str] = ["media_player"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Frontier Silicon from a config entry."""

    webfsapi_url = entry.data[CONF_WEBFSAPI_URL]
    pin = entry.data[CONF_PIN]
    use_session = entry.data[CONF_USE_SESSION]

    afsapi = AFSAPI(webfsapi_url, pin, use_session)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = afsapi

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
