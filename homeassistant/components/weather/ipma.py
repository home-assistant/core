"""
Support for IPMA weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.ipma/
"""
import logging
from datetime import timedelta

import async_timeout
import voluptuous as vol

from homeassistant.components.weather import (
    WeatherEntity, PLATFORM_SCHEMA, ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION, ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW, ATTR_FORECAST_TIME)
from homeassistant.const import \
    CONF_NAME, TEMP_CELSIUS, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['pyipma==1.1.3']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Instituto Português do Mar e Atmosfera'

ATTR_WEATHER_DESCRIPTION = "description"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

CONDITION_CLASSES = {
    'cloudy': [4, 5, 24, 25, 27],
    'fog': [16, 17, 26],
    'hail': [21, 22],
    'lightning': [19],
    'lightning-rainy': [20, 23],
    'partlycloudy': [2, 3],
    'pouring': [8, 11],
    'rainy': [6, 7, 9, 10, 12, 13, 14, 15],
    'snowy': [18],
    'snowy-rainy': [],
    'sunny': [1],
    'windy': [],
    'windy-variant': [],
    'exceptional': [],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the ipma platform."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    from pyipma import Station

    websession = async_get_clientsession(hass)
    with async_timeout.timeout(10, loop=hass.loop):
        station = await Station.get(websession, float(latitude),
                                    float(longitude))

    _LOGGER.debug("Initializing ipma weather: coordinates %s, %s",
                  latitude, longitude)

    async_add_entities([IPMAWeather(station, config)], True)


class IPMAWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, station, config):
        """Initialise the platform with a data instance and station name."""
        self._station_name = config.get(CONF_NAME, station.local)
        self._station = station
        self._condition = None
        self._forecast = None
        self._description = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update Condition and Forecast."""
        with async_timeout.timeout(10, loop=self.hass.loop):
            self._condition = await self._station.observation()
            self._forecast = await self._station.forecast()
            self._description = self._forecast[0].description

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the station."""
        return self._station_name

    @property
    def condition(self):
        """Return the current condition."""
        return next((k for k, v in CONDITION_CLASSES.items()
                     if self._forecast[0].idWeatherType in v), None)

    @property
    def temperature(self):
        """Return the current temperature."""
        return self._condition.temperature

    @property
    def pressure(self):
        """Return the current pressure."""
        return self._condition.pressure

    @property
    def humidity(self):
        """Return the name of the sensor."""
        return self._condition.humidity

    @property
    def wind_speed(self):
        """Return the current windspeed."""
        return self._condition.windspeed

    @property
    def wind_bearing(self):
        """Return the current wind bearing (degrees)."""
        return self._condition.winddirection

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def forecast(self):
        """Return the forecast array."""
        if self._forecast:
            fcdata_out = []
            for data_in in self._forecast:
                data_out = {}
                data_out[ATTR_FORECAST_TIME] = data_in.forecastDate
                data_out[ATTR_FORECAST_CONDITION] =\
                    next((k for k, v in CONDITION_CLASSES.items()
                          if int(data_in.idWeatherType) in v), None)
                data_out[ATTR_FORECAST_TEMP_LOW] = data_in.tMin
                data_out[ATTR_FORECAST_TEMP] = data_in.tMax
                data_out[ATTR_FORECAST_PRECIPITATION] = data_in.precipitaProb

                fcdata_out.append(data_out)

            return fcdata_out

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        data = dict()

        if self._description:
            data[ATTR_WEATHER_DESCRIPTION] = self._description

        return data
