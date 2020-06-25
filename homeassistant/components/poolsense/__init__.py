"""The PoolSense integration."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
from poolsense import PoolSense

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, update_coordinator

from .const import DOMAIN

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the PoolSense component."""
    # Make sure coordinator is initialized.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up PoolSense from a config entry."""
    await get_coordinator(hass, entry)

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


async def get_coordinator(hass, entry):
    """Get the data update coordinator."""
    if DOMAIN in hass.data:
        return hass.data[DOMAIN]

    async def async_get_data():
        _LOGGER.info("Run query to server")
        poolsense = PoolSense()
        with async_timeout.timeout(10):
            return await poolsense.get_poolsense_data(
                aiohttp_client.async_get_clientsession(hass),
                entry.data[CONF_EMAIL],
                entry.data[CONF_PASSWORD],
            )

    hass.data[DOMAIN] = update_coordinator.DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_data,
        update_interval=timedelta(hours=1),
    )
    await hass.data[DOMAIN].async_refresh()
    return hass.data[DOMAIN]
