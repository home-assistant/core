"""
Weather information for air and road temperature, provided by Trafikverket.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.trafikverket_weatherstation/
"""

import asyncio
from datetime import timedelta
import logging

import aiohttp
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_API_KEY, CONF_MONITORED_CONDITIONS, CONF_NAME)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pytrafikverket==0.1.5.8']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

CONF_ATTRIBUTION = "Data provided by Trafikverket API"
CONF_STATION = 'station'


SENSOR_TYPES = {
    'air_temp': ['Air temperature', '°C', 'air_temp'],
    'road_temp': ['Road temperature', '°C', 'road_temp'],
    'precipitation': ['Precipitation type', None, 'precipitationtype'],
    'wind_direction': ['Wind direction', '°', 'winddirection'],
    'wind_direction_text': ['Wind direction text', None, 'winddirectiontext'],
    'wind_speed': ['Wind speed', 'm/s', 'windforce'],
    'humidity': ['Humidity', '%', 'humidity'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_STATION): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        [vol.In(SENSOR_TYPES)],
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Trafikverket sensor platform."""
    from pytrafikverket.trafikverket_weather import TrafikverketWeather

    sensor_name = config[CONF_NAME]
    sensor_api = config[CONF_API_KEY]
    sensor_station = config[CONF_STATION]

    web_session = async_get_clientsession(hass)

    weather_api = TrafikverketWeather(web_session, sensor_api)

    dev = []
    for condition in config[CONF_MONITORED_CONDITIONS]:
        dev.append(TrafikverketWeatherStation(
            weather_api, sensor_name, condition, sensor_station))

    if dev:
        async_add_entities(dev, True)


class TrafikverketWeatherStation(Entity):
    """Representation of a Trafikverket sensor."""

    def __init__(self, weather_api, name, sensor_type, sensor_station):
        """Initialize the sensor."""
        self._client = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self._type = sensor_type
        self._state = None
        self._unit = SENSOR_TYPES[sensor_type][1]
        self._station = sensor_station
        self._weather_api = weather_api
        self._attributes = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }
        self._weather = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._client, self._name)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from Trafikverket and updates the states."""
        try:
            self._weather = await self._weather_api.async_get_weather(
                self._station)
            self._state = getattr(
                self._weather,
                SENSOR_TYPES[self._type][2])
        except (asyncio.TimeoutError,
                aiohttp.ClientError, ValueError) as error:
            _LOGGER.error("Couldn't fetch weather data: %s", error)
