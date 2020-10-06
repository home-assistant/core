"""The FAA Delays integration."""
import asyncio
import logging

from aiohttp import ClientConnectionError
from faadelays import Airport
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the FAA Delays component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up FAA Delays from a config entry."""
    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        faadata = FAAData(
            Airport(
                entry.data[CONF_ID],
                websession,
            )
        )
        await faadata.async_update()
        hass.data[DOMAIN][entry.entry_id] = faadata
    except ClientConnectionError as err:
        _LOGGER.error("Connection error during setup: %s", err)
        raise PlatformNotReady from err

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


class FAAData:
    """Define a data object to retrieve info from FAA API."""

    def __init__(self, client):
        """Initialize."""
        self.client = client

    async def async_update(self):
        """Update sensor data."""
        try:
            await self.client.update()
        except ClientConnectionError as err:
            _LOGGER.error("Connection error during data update: %s", err)
