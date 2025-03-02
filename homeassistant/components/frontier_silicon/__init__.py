"""The Frontier Silicon integration."""

from __future__ import annotations

import logging

from afsapi import AFSAPI, ConnectionError as FSConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PIN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_WEBFSAPI_URL

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)

type FrontierSiliconConfigEntry = ConfigEntry[AFSAPI]


async def async_setup_entry(
    hass: HomeAssistant, entry: FrontierSiliconConfigEntry
) -> bool:
    """Set up Frontier Silicon from a config entry."""

    webfsapi_url = entry.data[CONF_WEBFSAPI_URL]
    pin = entry.data[CONF_PIN]

    afsapi = AFSAPI(webfsapi_url, pin)

    try:
        await afsapi.get_power()
    except FSConnectionError as exception:
        raise ConfigEntryNotReady from exception

    entry.runtime_data = afsapi

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FrontierSiliconConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
