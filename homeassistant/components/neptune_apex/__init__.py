"""The Neptune Apex integration."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
from pynepsys import Apex
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["light", "sensor"]

NEPTUNE_APEX = "neptune_apex"
NEPTUNE_APEX_COORDINATOR = "neptune_apex_coordinator"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Neptune Apex component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Neptune Apex from a config entry."""
    apex = Apex(entry.data["host"], entry.data["username"], entry.data["password"])
    hass.data[NEPTUNE_APEX] = apex

    async def async_update_data():
        """Fetch data for all outlets and probes at once."""
        try:
            async with async_timeout.timeout(10):
                await apex.fetch_current_state()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Apex: {err}")
        return apex

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="neptune_apex",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=30),
    )
    hass.data[NEPTUNE_APEX_COORDINATOR] = coordinator

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

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
