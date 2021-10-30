"""The Wallbox integration."""
from datetime import timedelta
from http import HTTPStatus
import logging

import requests
from wallbox import Wallbox

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CONNECTIONS,
    CONF_DATA_KEY,
    CONF_MAX_CHARGING_CURRENT_KEY,
    CONF_ROUND,
    CONF_SENSOR_TYPES,
    CONF_STATION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number"]
UPDATE_INTERVAL = 30


class WallboxCoordinator(DataUpdateCoordinator):
    """Wallbox Coordinator class."""

    def __init__(self, station, wallbox, hass):
        """Initialize."""
        self._station = station
        self._wallbox = wallbox

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    def _authenticate(self):
        """Authenticate using Wallbox API."""
        try:
            self._wallbox.authenticate()
            return True
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == HTTPStatus.FORBIDDEN:
                raise InvalidAuth from wallbox_connection_error
            raise ConnectionError from wallbox_connection_error

    def _validate(self):
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
            data[CONF_MAX_CHARGING_CURRENT_KEY] = data[CONF_DATA_KEY][
                CONF_MAX_CHARGING_CURRENT_KEY
            ]

            filtered_data = {k: data[k] for k in CONF_SENSOR_TYPES if k in data}

            for key, value in filtered_data.items():
                if (sensor_round := CONF_SENSOR_TYPES[key][CONF_ROUND]) is not None:
                    try:
                        filtered_data[key] = round(value, sensor_round)
                    except TypeError:
                        _LOGGER.debug("Cannot format %s", key)

            return filtered_data
        except requests.exceptions.HTTPError as wallbox_connection_error:
            raise ConnectionError from wallbox_connection_error

    def _set_charging_current(self, charging_current):
        """Set maximum charging current for Wallbox."""
        try:
            self._authenticate()
            self._wallbox.setMaxChargingCurrent(self._station, charging_current)
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 403:
                raise InvalidAuth from wallbox_connection_error
            raise ConnectionError from wallbox_connection_error

    async def async_set_charging_current(self, charging_current):
        """Set maximum charging current for Wallbox."""
        await self.hass.async_add_executor_job(
            self._set_charging_current, charging_current
        )
        await self.async_request_refresh()

    async def _async_update_data(self) -> bool:
        """Get new sensor data for Wallbox component."""
        data = await self.hass.async_add_executor_job(self._get_data)
        return data

    async def async_validate_input(self) -> bool:
        """Get new sensor data for Wallbox component."""
        data = await self.hass.async_add_executor_job(self._validate)
        return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wallbox from a config entry."""
    wallbox = Wallbox(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    wallbox_coordinator = WallboxCoordinator(
        entry.data[CONF_STATION],
        wallbox,
        hass,
    )

    await wallbox_coordinator.async_validate_input()

    await wallbox_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {CONF_CONNECTIONS: {}})
    hass.data[DOMAIN][CONF_CONNECTIONS][entry.entry_id] = wallbox_coordinator

    for platform in PLATFORMS:

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][CONF_CONNECTIONS].pop(entry.entry_id)

    return unload_ok


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
