"""The Whirlpool Sixth Sense integration."""
import logging

import aiohttp
from whirlpool.auth import Auth

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import AUTH_INSTANCE_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Whirlpool Sixth Sense from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    auth = Auth(entry.data["username"], entry.data["password"])
    try:
        await auth.do_auth(store=False)
    except aiohttp.ClientError as ex:
        raise ConfigEntryNotReady("Cannot connect") from ex

    if not auth.is_access_token_valid():
        _LOGGER.error("Authentication failed")
        return False

    hass.data[DOMAIN][entry.entry_id] = {AUTH_INSTANCE_KEY: auth}

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
