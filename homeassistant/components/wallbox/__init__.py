"""The Wallbox integration."""
import asyncio
import logging

import requests
from wallbox import Wallbox

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_CONNECTIONS, CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


class WallboxHub:
    """Wallbox Hub class."""

    def __init__(self, station, username, password):
        """Initialize."""
        self._station = station
        self._username = username
        self._password = password
        self._wallbox = Wallbox(self._username, self._password)

    def _authenticate(self):
        """Authenticate using Wallbox API."""
        try:
            self._wallbox.authenticate()
            return True
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 403:
                raise InvalidAuth from wallbox_connection_error
            raise ConnectionError from wallbox_connection_error

    def _get_data(self):
        """Get new sensor data for Wallbox component."""
        try:
            self._authenticate()
            data = self._wallbox.getChargerStatus(self._station)
            return data
        except requests.exceptions.HTTPError as wallbox_connection_error:
            raise ConnectionError from wallbox_connection_error

    async def async_authenticate(self, hass) -> bool:
        """Authenticate using Wallbox API."""
        return await hass.async_add_executor_job(self._authenticate)

    async def async_get_data(self, hass) -> bool:
        """Get new sensor data for Wallbox component."""
        data = await hass.async_add_executor_job(self._get_data)
        return data


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Wallbox component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Wallbox from a config entry."""
    wallbox = WallboxHub(
        entry.data[CONF_STATION],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    await wallbox.async_authenticate(hass)

    hass.data.setdefault(DOMAIN, {CONF_CONNECTIONS: {}})
    hass.data[DOMAIN][CONF_CONNECTIONS][entry.entry_id] = wallbox

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
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
        hass.data[DOMAIN]["connections"].pop(entry.entry_id)

    return unload_ok


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

    def __init__(self, msg=""):
        """Create a log record."""
        super().__init__()
        _LOGGER.error("Cannot connect to Wallbox API. %s", msg)


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

    def __init__(self, msg=""):
        """Create a log record."""
        super().__init__()
        _LOGGER.error("Cannot authenticate with Wallbox API. %s", msg)
