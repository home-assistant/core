"""The Epion integration."""
from __future__ import annotations

import socket

from requests.exceptions import ConnectTimeout, HTTPError
from epion import Epion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle


from .const import CONF_SITE_ID, DATA_API_CLIENT, DOMAIN, LOGGER, REFRESH_INTERVAL

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Epion from a config entry."""
    api = Epion(entry.data[CONF_API_KEY])

    try:
        response = await hass.async_add_executor_job(api.get_current)
    except (ConnectTimeout, HTTPError, socket.gaierror) as ex:
        LOGGER.error("Could not retrieve details from Epion API")
        raise ConfigEntryNotReady from ex

    if len(response["devices"]) == 0:
        LOGGER.error("Epion account is not active")
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_API_CLIENT: EpionBase(hass, api, response)}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Epion config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok

class EpionBase:
    """An object to hold the Epion API instance."""

    def __init__(self, hass, epion, last_response):
        """Initialize the Epion API base."""
        self.hass = hass
        self.epion = epion
        self.last_response = last_response
        self.device_data = {}

    def updateNow(self):
        self.last_response = self.epion.get_current()
        for epion_device in self.last_response['devices']:
            self.device_data[epion_device['deviceId']] = epion_device

    @Throttle(REFRESH_INTERVAL)
    async def async_update(self):
        """Update all Epion data."""
        await self.hass.async_add_executor_job(self.updateNow)