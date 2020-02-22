"""The National Weather Service integration."""
import asyncio
import datetime
import logging

import aiohttp
from pynws import SimpleNWS
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)

_INDIVIDUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
        vol.Optional(CONF_SCAN_INTERVAL): vol.All(cv.positive_int, vol.Range(min=5)),
        vol.Optional(CONF_STATION): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [_INDIVIDUAL_SCHEMA])}, extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["weather"]


def unique_id(latitude, longitude):
    """Return unique id for entries in configuration."""
    return f"{DOMAIN}_{latitude}_{longitude}"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the National Weather Service integration."""
    if DOMAIN not in config:
        return True

    hass.data[DOMAIN] = hass.data.get(DOMAIN, {})
    for entry in config[DOMAIN]:
        latitude = entry.get(CONF_LATITUDE, hass.config.latitude)
        longitude = entry.get(CONF_LONGITUDE, hass.config.longitude)
        api_key = entry[CONF_API_KEY]
        station = entry.get(CONF_STATION)
        scan_interval = entry.get(CONF_SCAN_INTERVAL, 10)

        client_session = async_get_clientsession(hass)

        if unique_id(latitude, longitude) in hass.data[DOMAIN]:
            _LOGGER.error(
                "Duplicate entry in config: latitude %s  latitude: %s",
                latitude,
                longitude,
            )
            continue

        nws_data = NwsData(hass, latitude, longitude, api_key, client_session)

        try:
            await nws_data.async_set_station(station)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error automatically setting station: %s", str(err))
            return False

        await nws_data.async_update()

        hass.data[DOMAIN][unique_id(latitude, longitude)] = nws_data

        scan_time = datetime.timedelta(minutes=scan_interval)
        async_track_time_interval(hass, nws_data.async_update, scan_time)

        for component in PLATFORMS:
            hass.async_create_task(
                discovery.async_load_platform(hass, component, DOMAIN, {}, config)
            )

    return True


class NwsData:
    """Data class for National Weather Service integration."""

    def __init__(self, hass, latitude, longitude, api_key, websession):
        """Initialize the data."""
        self.hass = hass
        self.latitude = latitude
        self.longitude = longitude
        ha_api_key = f"{api_key} homeassistant"
        self.nws = SimpleNWS(latitude, longitude, ha_api_key, websession)

        self.update_observation_success = True
        self.update_forecast_success = True
        self.update_forecast_hourly_success = True

    async def async_set_station(self, station):
        """
        Set to desired station.

        If None, nearest station is used.
        """
        await self.nws.set_station(station)
        _LOGGER.debug("Nearby station list: %s", self.nws.stations)

    @property
    def station(self):
        """Return station name."""
        return self.nws.station

    @property
    def observation(self):
        """Return observation."""
        return self.nws.observation

    @property
    def forecast(self):
        """Return day+night forecast."""
        return self.nws.forecast

    @property
    def forecast_hourly(self):
        """Return hourly forecast."""
        return self.nws.forecast_hourly

    async def async_update(self, now=None):
        """Update all data."""
        try:
            _LOGGER.debug("Updating observation for station %s", self.station)
            await self.nws.update_observation()

            if not self.update_observation_success:
                _LOGGER.warning(
                    "Success updating observation for station %s", self.station
                )
                self.update_observation_success = True
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            if self.update_observation_success:
                _LOGGER.warning(
                    "Error updating observation for station %s: %s", self.station, err
                )
            self.update_observation_success = False

        try:
            _LOGGER.debug("Updating forecast for station %s", self.station)
            await self.nws.update_forecast()

            if not self.update_forecast_success:
                _LOGGER.warning(
                    "Success updating forecast for station %s", self.station
                )
                self.update_forecast_success = True
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            if self.update_forecast_success:
                _LOGGER.warning(
                    "Error updating forecast for station %s: %s", self.station, err
                )
            self.update_forecast_success = False

        try:
            _LOGGER.debug("Updating forecast hourly for station %s", self.station)
            await self.nws.update_forecast_hourly()

            if not self.update_forecast_hourly_success:
                _LOGGER.warning(
                    "Success updating forecast hourly for station %s", self.station
                )
                self.update_forecast_hourly_success = True
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            if self.update_forecast_hourly_success:
                _LOGGER.warning(
                    "Error updating forecast hourly for station %s: %s",
                    self.station,
                    err,
                )
            self.update_forecast_hourly_success = False
        async_dispatcher_send(self.hass, unique_id(self.latitude, self.longitude))
        _LOGGER.debug("Updating complete for station %s", self.station)
