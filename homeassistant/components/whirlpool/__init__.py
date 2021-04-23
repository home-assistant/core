"""The Whirlpool Sixth Sense integration."""
import asyncio
import logging

import aiohttp
from whirlpool.auth import Auth

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import AUTH_INSTANCE_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Whirlpool Sixth Sense from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    auth = Auth(entry.data["username"], entry.data["password"])
    try:
        await auth.load_auth_file()
    except aiohttp.ClientConnectionError:
        _LOGGER.error("Connection error")
        return False

    if not auth.is_access_token_valid():
        _LOGGER.error("Authentication failed")
        return False

    hass.data[DOMAIN][entry.entry_id] = {AUTH_INSTANCE_KEY: auth}

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
