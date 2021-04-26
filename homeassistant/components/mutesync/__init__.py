"""The mütesync integration."""
from __future__ import annotations

import asyncio

import aiohttp
import async_timeout
import mutesync

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS = ["binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up mütesync from a config entry."""
    client = hass.data.setdefault(DOMAIN, {})[entry.entry_id] = mutesync.PyMutesync(
        entry.data["token"],
        entry.data["host"],
        hass.helpers.aiohttp_client.async_get_clientsession(),
    )
    try:
        async with async_timeout.timeout(10):
            await client.get_state()
    except (aiohttp.ClientError, asyncio.TimeoutError) as error:
        raise ConfigEntryNotReady("cannot_connect") from error

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
