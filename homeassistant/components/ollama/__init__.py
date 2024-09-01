"""The Ollama integration."""

from __future__ import annotations

import asyncio
import logging

import httpx
import ollama

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_KEEP_ALIVE,
    CONF_MAX_HISTORY,
    CONF_MODEL,
    CONF_NUM_CTX,
    CONF_PROMPT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "CONF_URL",
    "CONF_PROMPT",
    "CONF_MODEL",
    "CONF_MAX_HISTORY",
    "CONF_NUM_CTX",
    "CONF_KEEP_ALIVE",
    "DOMAIN",
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (Platform.CONVERSATION,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ollama from a config entry."""
    settings = {**entry.data, **entry.options}
    client = ollama.AsyncClient(host=settings[CONF_URL])
    try:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            await client.list()
    except (TimeoutError, httpx.ConnectError) as err:
        raise ConfigEntryNotReady(err) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ollama."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
