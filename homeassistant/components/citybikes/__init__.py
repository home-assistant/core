"""The CityBikes integration."""

from __future__ import annotations

import aiohttp
import sys
from citybikes import __version__ as CITYBIKES_CLIENT_VERSION
from citybikes.asyncio import Client as CitybikesClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import APPLICATION_NAME, __version__
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import CityBikesCoordinator, HA_USER_AGENT, REQUEST_TIMEOUT

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CityBikes from a config entry."""
    client = CitybikesClient(user_agent=HA_USER_AGENT, timeout=REQUEST_TIMEOUT)
    coordinator = CityBikesCoordinator(hass, client, entry.data["network"], entry)

    setup_successful = False
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        setup_successful = True
    except ConfigEntryNotReady:
        raise
    finally:
        if not setup_successful:
            await client.close()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: CityBikesCoordinator = entry.runtime_data
        await coordinator.client.close()

    return unload_ok
