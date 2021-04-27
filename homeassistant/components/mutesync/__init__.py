"""The mütesync integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import async_timeout
import mutesync

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator

from .const import DOMAIN

PLATFORMS = ["binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up mütesync from a config entry."""
    client = mutesync.PyMutesync(
        entry.data["token"],
        entry.data["host"],
        hass.helpers.aiohttp_client.async_get_clientsession(),
    )

    async def update_data():
        """Update the data."""
        async with async_timeout.timeout(5):
            return await client.get_state()

    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = update_coordinator.DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_interval=timedelta(seconds=10),
        update_method=update_data,
    )
    await coordinator.async_config_entry_first_refresh()

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
