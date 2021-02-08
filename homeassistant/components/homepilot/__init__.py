"""The Rademacher HomePilot integration."""

import asyncio
from datetime import timedelta
import logging

from pyhomepilot.api import HomePilotAPI
from pyhomepilot.auth import Auth

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["cover"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Rademacher HomePilot component."""
    hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Rademacher HomePilot from a config entry."""
    session = aiohttp_client.async_create_clientsession(hass)
    auth = Auth(session, entry.data["host"], entry.data.get("password"))

    if "password" in entry.data:
        await auth.async_login()

    api = HomePilotAPI(auth)

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            return {device.uid: device for device in await api.async_get_all_devices()}
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="homepilot",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )

    # Fetch initial data
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {"api": api, "coordinator": coordinator}

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
