"""Weather information for air and road temperature (by Trafikverket)."""

import asyncio
from datetime import timedelta
import logging

import aiohttp
from pytrafikverket.trafikverket_weather import TrafikverketWeather
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Trafikverket"
ATTR_MEASURE_TIME = "measure_time"
ATTR_ACTIVE = "active"

CONF_STATION = "station"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

SCAN_INTERVAL = timedelta(seconds=300)

SENSOR_TYPES = {
    "air_temp": [
        "Air temperature",
        TEMP_CELSIUS,
        "air_temp",
        "mdi:thermometer",
        DEVICE_CLASS_TEMPERATURE,
    ],
    "road_temp": [
        "Road temperature",
        TEMP_CELSIUS,
        "road_temp",
        "mdi:thermometer",
        DEVICE_CLASS_TEMPERATURE,
    ],
    "precipitation": [
        "Precipitation type",
        None,
        "precipitationtype",
        "mdi:weather-snowy-rainy",
        None,
    ],
    "wind_direction": [
        "Wind direction",
        DEGREE,
        "winddirection",
        "mdi:flag-triangle",
        None,
    ],
    "wind_direction_text": [
        "Wind direction text",
        None,
        "winddirectiontext",
        "mdi:flag-triangle",
        None,
    ],
    "wind_speed": [
        "Wind speed",
        SPEED_METERS_PER_SECOND,
        "windforce",
        "mdi:weather-windy",
        None,
    ],
    "humidity": [
        "Humidity",
        UNIT_PERCENTAGE,
        "humidity",
        "mdi:water-percent",
        DEVICE_CLASS_HUMIDITY,
    ],
    "precipitation_amount": [
        "Precipitation amount",
        "mm",
        "precipitation_amount",
        "mdi:cup-water",
        None,
    ],
    "precipitation_amountname": [
        "Precipitation name",
        None,
        "precipitation_amountname",
        "mdi:weather-pouring",
        None,
    ],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_STATION): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): [vol.In(SENSOR_TYPES)],
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Trafikverket sensor platform."""

    sensor_name = config[CONF_NAME]
    sensor_api = config[CONF_API_KEY]
    sensor_station = config[CONF_STATION]

    web_session = async_get_clientsession(hass)

    weather_api = TrafikverketWeather(web_session, sensor_api)

    dev = []
    for condition in config[CONF_MONITORED_CONDITIONS]:
        dev.append(
            TrafikverketWeatherStation(
                weather_api, sensor_name, condition, sensor_station
            )
        )

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
        self._icon = SENSOR_TYPES[sensor_type][3]
        self._device_class = SENSOR_TYPES[sensor_type][4]
        self._weather = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._client} {self._name}"

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of Trafikverket Weatherstation."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_ACTIVE: self._weather.active,
            ATTR_MEASURE_TIME: self._weather.measure_time,
        }

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

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
            self._weather = await self._weather_api.async_get_weather(self._station)
            self._state = getattr(self._weather, SENSOR_TYPES[self._type][2])
        except (asyncio.TimeoutError, aiohttp.ClientError, ValueError) as error:
            _LOGGER.error("Could not fetch weather data: %s", error)
