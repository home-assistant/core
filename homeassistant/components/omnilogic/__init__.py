"""The Omnilogic integration."""
import asyncio
import json
import logging
from datetime import timedelta

import async_timeout
from homeassistant.exceptions import ConfigEntryNotReady


import aiohttp
from omnilogic.omnilogic import OmniLogic
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Omnilogic component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Omnilogic from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    # for component in PLATFORMS:
    #     hass.async_create_task(
    #         hass.config_entries.async_forward_entry_setup(entry, component)
    #     )

    conf = entry.data
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    session = async_get_clientsession(hass)
    coordinator = OmnilogicUpdateCoordinator(
        hass, username, password, session, timedelta(minutes=1)
    )
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

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


class OmnilogicUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Omnilogic data"""

    def __init__(self, hass, username, password, session, update_interval):
        """Initialize"""
        _LOGGER.info("__INIT__")
        self.name = "test"
        self.api = OmniLogic(username, password)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self):
        """update data"""
        _LOGGER.info("async_update_data")

        with async_timeout.timeout(20):
            try:
                _LOGGER.info("fetching data")
                telemetry_data = await self.api.get_telemetry_data()
                _LOGGER.info("Data updated!")
                # need to find out where/when to close api connection
                # await self.api.close()
                return telemetry_data
            except ImportError as err:
                raise UpdateFailed(err)

