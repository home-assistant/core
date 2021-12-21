"""The sensibo component."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
import async_timeout
import pysensibo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import _INITIAL_FETCH_FIELDS, DOMAIN, PLATFORMS, TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sensibo from a config entry."""
    title = entry.title

    client = pysensibo.SensiboClient(
        entry.data[CONF_API_KEY], session=async_get_clientsession(hass), timeout=TIMEOUT
    )
    devicelist = []
    try:
        async with async_timeout.timeout(TIMEOUT):
            for dev in await client.async_get_devices(_INITIAL_FETCH_FIELDS):
                devicelist.append(dev)
    except (
        aiohttp.client_exceptions.ClientConnectorError,
        asyncio.TimeoutError,
        pysensibo.SensiboError,
    ) as err:
        raise ConfigEntryNotReady("Failed to get devices from Sensibo servers") from err

    if not devicelist:
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"devices": devicelist}
    hass.data[DOMAIN][entry.entry_id]["client"] = client

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    _LOGGER.debug("Loaded entry for %s", title)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Sensibo config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    title = entry.title

    del hass.data[DOMAIN][entry.entry_id]
    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    if unload_ok:
        _LOGGER.debug("Unloaded entry for %s", title)
        return unload_ok

    return False
