"""The Garages Amsterdam integration."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
import garages_amsterdam

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, update_coordinator

from .const import DOMAIN

PLATFORMS = ["binary_sensor", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Garages Amsterdam component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Garages Amsterdam from a config entry."""
    await get_coordinator(hass)
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

    return unload_ok


async def get_coordinator(hass):
    """Get the data update coordinator."""
    if DOMAIN in hass.data:
        return hass.data[DOMAIN]

    async def async_get_garages():
        with async_timeout.timeout(10):
            return {
                garage.garage_name: garage
                for garage in await garages_amsterdam.get_garages(
                    aiohttp_client.async_get_clientsession(hass)
                )
            }

    hass.data[DOMAIN] = update_coordinator.DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_garages,
        update_interval=timedelta(minutes=10),
    )
    await hass.data[DOMAIN].async_refresh()
    return hass.data[DOMAIN]
