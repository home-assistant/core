"""The National Weather Service integration."""
import asyncio
import datetime
import logging

import aiohttp
from pynws import SimpleNWS
import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
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
        vol.Optional(CONF_STATION): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [_INDIVIDUAL_SCHEMA])}, extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["weather"]

DEFAULT_SCAN_INTERVAL = datetime.timedelta(minutes=10)


def base_unique_id(latitude, longitude):
    """Return unique id for entries in configuration."""
    return f"{latitude}_{longitude}"


def signal_unique_id(latitude, longitude):
    """Return unique id for signaling to entries in configuration from component."""
    return f"{DOMAIN}_{base_unique_id(latitude,longitude)}"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the National Weather Service integration."""
    if DOMAIN not in config:
        return True

    hass.data[DOMAIN] = hass.data.get(DOMAIN, {})
    for entry in config[DOMAIN]:
        latitude = entry.get(CONF_LATITUDE, hass.config.latitude)
        longitude = entry.get(CONF_LONGITUDE, hass.config.longitude)
        api_key = entry[CONF_API_KEY]

        client_session = async_get_clientsession(hass)

        if base_unique_id(latitude, longitude) in hass.data[DOMAIN]:
            _LOGGER.error(
                "Duplicate entry in config: latitude %s  latitude: %s",
                latitude,
                longitude,
            )
            continue

        nws_data = NwsData(hass, latitude, longitude, api_key, client_session)
        hass.data[DOMAIN][base_unique_id(latitude, longitude)] = nws_data
        async_track_time_interval(hass, nws_data.async_update, DEFAULT_SCAN_INTERVAL)

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

    @staticmethod
    async def _async_update_item(update_call, update_type, station_name, success):
        try:
            _LOGGER.debug("Updating %s for station %s", update_type, station_name)
            await update_call()

            if success:
                _LOGGER.warning(
                    "Success updating %s for station %s", update_type, station_name
                )
                success = True
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            if success:
                _LOGGER.warning(
                    "Error updating %s for station %s: %s",
                    update_type,
                    station_name,
                    err,
                )
            success = False

    async def async_update(self, now=None):
        """Update all data."""

        await self._async_update_item(
            self.nws.update_observation,
            "observation",
            self.station,
            self.update_observation_success,
        )
        await self._async_update_item(
            self.nws.update_forecast,
            "forecast",
            self.station,
            self.update_forecast_success,
        )
        await self._async_update_item(
            self.nws.update_forecast_hourly,
            "forecast_hourly",
            self.station,
            self.update_forecast_hourly_success,
        )

        async_dispatcher_send(
            self.hass, signal_unique_id(self.latitude, self.longitude)
        )
