"""The sensibo component."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
import async_timeout
import pysensibo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    _INITIAL_FETCH_FIELDS,
    ALL,
    DOMAIN as SENSIBO_DOMAIN,
    PLATFORMS,
    TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sensibo from a config entry."""
    title = entry.title

    client = pysensibo.SensiboClient(
        entry.data[CONF_API_KEY], session=async_get_clientsession(hass), timeout=TIMEOUT
    )
    hass.data.setdefault(SENSIBO_DOMAIN, {})
    hass.data[SENSIBO_DOMAIN][entry.entry_id] = {"devices": []}

    try:
        async with async_timeout.timeout(TIMEOUT):
            for dev in await client.async_get_devices(_INITIAL_FETCH_FIELDS):
                if entry.data[CONF_ID] == ALL or dev["id"] in entry.data[CONF_ID]:
                    hass.data[SENSIBO_DOMAIN][entry.entry_id]["devices"].append(dev)
    except (
        aiohttp.client_exceptions.ClientConnectorError,
        asyncio.TimeoutError,
        pysensibo.SensiboError,
    ) as err:
        _LOGGER.error("Failed to get devices from Sensibo servers")
        raise ConfigEntryNotReady from err

    if hass.data[SENSIBO_DOMAIN][entry.entry_id]["devices"]:
        hass.config_entries.async_setup_platforms(entry, PLATFORMS)
        _LOGGER.debug("Loaded entry for %s", title)
        return True

    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Sensibo config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    title = entry.title

    del hass.data[SENSIBO_DOMAIN][entry.entry_id]
    if not hass.data[SENSIBO_DOMAIN]:
        del hass.data[SENSIBO_DOMAIN]

    if unload_ok:
        _LOGGER.debug("Unloaded entry for %s", title)
        return unload_ok

    return False
