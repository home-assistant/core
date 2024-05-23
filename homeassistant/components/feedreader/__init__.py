"""Support for RSS/Atom feeds."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_MAX_ENTRIES,
    CONF_URLS,
    DEFAULT_MAX_ENTRIES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import FeedReaderCoordinator, StoredData

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Required(CONF_URLS): vol.All(cv.ensure_list, [cv.url]),
            vol.Optional(
                CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
            ): cv.time_period,
            vol.Optional(
                CONF_MAX_ENTRIES, default=DEFAULT_MAX_ENTRIES
            ): cv.positive_int,
        }
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Feedreader component."""
    urls: list[str] = config[DOMAIN][CONF_URLS]
    if not urls:
        return False

    scan_interval: timedelta = config[DOMAIN][CONF_SCAN_INTERVAL]
    max_entries: int = config[DOMAIN][CONF_MAX_ENTRIES]
    old_data_file = hass.config.path(f"{DOMAIN}.pickle")
    storage = StoredData(hass, old_data_file)
    await storage.async_setup()
    feeds = [
        FeedReaderCoordinator(hass, url, scan_interval, max_entries, storage)
        for url in urls
    ]

    await asyncio.gather(*[feed.async_refresh() for feed in feeds])

    # workaround until we have entities to update
    [feed.async_add_listener(lambda: None) for feed in feeds]

    return True
