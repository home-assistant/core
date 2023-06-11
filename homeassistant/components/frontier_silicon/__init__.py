"""The Frontier Silicon integration."""
from __future__ import annotations

import logging

from afsapi import AFSAPI, ConnectionError as FSConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_PIN, CONF_WEBFSAPI_URL, DOMAIN

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Frontier Silicon from a config entry."""

    webfsapi_url = entry.data[CONF_WEBFSAPI_URL]
    pin = entry.data[CONF_PIN]

    afsapi = AFSAPI(webfsapi_url, pin)

    try:
        await afsapi.get_power()
    except FSConnectionError as exception:
        raise ConfigEntryNotReady from exception

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = afsapi

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
