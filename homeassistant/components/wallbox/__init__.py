"""The Wallbox integration."""
from datetime import timedelta
import logging

import requests
from wallbox import Wallbox

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CONNECTIONS, CONF_ROUND, CONF_SENSOR_TYPES, CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
UPDATE_INTERVAL = 30


class WallboxHub:
    """Wallbox Hub class."""

    def __init__(self, station, username, password, hass):
        """Initialize."""
        self._station = station
        self._username = username
        self._password = password
        self._wallbox = Wallbox(self._username, self._password)
        self._hass = hass
        self._coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="wallbox",
            update_method=self.async_get_data,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

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

            filtered_data = {k: data[k] for k in CONF_SENSOR_TYPES if k in data}

            for key, value in filtered_data.items():
                sensor_round = CONF_SENSOR_TYPES[key][CONF_ROUND]
                if sensor_round:
                    try:
                        filtered_data[key] = round(value, sensor_round)
                    except TypeError:
                        _LOGGER.debug("Cannot format %s", key)

            return filtered_data
        except requests.exceptions.HTTPError as wallbox_connection_error:
            raise ConnectionError from wallbox_connection_error

    async def async_coordinator_first_refresh(self):
        """Refresh coordinator for the first time."""
        await self._coordinator.async_config_entry_first_refresh()

    async def async_authenticate(self) -> bool:
        """Authenticate using Wallbox API."""
        return await self._hass.async_add_executor_job(self._authenticate)

    async def async_get_data(self) -> bool:
        """Get new sensor data for Wallbox component."""
        data = await self._hass.async_add_executor_job(self._get_data)
        return data

    @property
    def coordinator(self):
        """Return the coordinator."""
        return self._coordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wallbox from a config entry."""
    wallbox = WallboxHub(
        entry.data[CONF_STATION],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        hass,
    )

    await wallbox.async_authenticate()

    await wallbox.async_coordinator_first_refresh()

    hass.data.setdefault(DOMAIN, {CONF_CONNECTIONS: {}})
    hass.data[DOMAIN][CONF_CONNECTIONS][entry.entry_id] = wallbox

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN]["connections"].pop(entry.entry_id)

    return unload_ok


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
