"""The Bbox integration."""

from __future__ import annotations

import logging

from aiobbox import BboxApi
from aiohttp import CookieJar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import CONF_BASE_URL
from .coordinator import BboxRouter

type BboxConfigEntry = ConfigEntry[BboxRouter]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BboxConfigEntry) -> bool:
    """Set up Bbox from a config entry."""
    base_url = entry.data[CONF_BASE_URL]
    password = entry.data[CONF_PASSWORD]

    # Create dedicated session with cookie support for Bbox authentication
    session = aiohttp_client.async_create_clientsession(
        hass,
        cookie_jar=CookieJar(unsafe=True),
    )

    client = BboxApi(
        password=password,
        base_url=base_url,
        timeout=10,
        session=session,
    )
    await client.authenticate()

    coordinator = BboxRouter(hass, client, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BboxConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Clean up coordinator and client sessions
        if hasattr(entry, "runtime_data"):
            await entry.runtime_data.async_shutdown()
    return unload_ok
