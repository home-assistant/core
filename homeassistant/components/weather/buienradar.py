"""
Support for Buienradar.nl weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.buienradar/
"""
import logging
import asyncio

import voluptuous as vol

from homeassistant.components.weather import (
    WeatherEntity, PLATFORM_SCHEMA, ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP, ATTR_FORECAST_TEMP_LOW, ATTR_FORECAST_TIME)
from homeassistant.const import \
    CONF_NAME, TEMP_CELSIUS, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers import config_validation as cv
# Reuse data and API logic from the sensor implementation
from homeassistant.components.sensor.buienradar import (
    BrData)

REQUIREMENTS = ['buienradar==0.91']

_LOGGER = logging.getLogger(__name__)

DATA_CONDITION = 'buienradar_condition'

DEFAULT_TIMEFRAME = 60

CONF_FORECAST = 'forecast'


CONDITION_CLASSES = {
    'cloudy': ['c', 'p'],
    'fog': ['d', 'n'],
    'hail': [],
    'lightning': ['g'],
    'lightning-rainy': ['s'],
    'partlycloudy': ['b', 'j', 'o', 'r'],
    'pouring': ['l', 'q'],
    'rainy': ['f', 'h', 'k', 'm'],
    'snowy': ['u', 'i', 'v', 't'],
    'snowy-rainy': ['w'],
    'sunny': ['a'],
    'windy': [],
    'windy-variant': [],
    'exceptional': [],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_FORECAST, default=True): cv.boolean,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up the buienradar platform."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    coordinates = {CONF_LATITUDE:  float(latitude),
                   CONF_LONGITUDE: float(longitude)}

    # create weather data:
    data = BrData(hass, coordinates, DEFAULT_TIMEFRAME, None)
    # create weather device:
    _LOGGER.debug("Initializing buienradar weather: coordinates %s",
                  coordinates)

    # create condition helper
    if DATA_CONDITION not in hass.data:
        cond_keys = [str(chr(x)) for x in range(97, 123)]
        hass.data[DATA_CONDITION] = dict.fromkeys(cond_keys)
        for cond, condlst in CONDITION_CLASSES.items():
            for condi in condlst:
                hass.data[DATA_CONDITION][condi] = cond

    async_add_entities([BrWeather(data, config)])

    # schedule the first update in 1 minute from now:
    yield from data.schedule_update(1)


class BrWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, data, config):
        """Initialise the platform with a data instance and station name."""
        self._stationname = config.get(CONF_NAME, None)
        self._forecast = config.get(CONF_FORECAST)
        self._data = data

    @property
    def attribution(self):
        """Return the attribution."""
        return self._data.attribution

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._stationname or 'BR {}'.format(self._data.stationname
                                                   or '(unknown station)')

    @property
    def condition(self):
        """Return the current condition."""
        from buienradar.buienradar import (CONDCODE)
        if self._data and self._data.condition:
            ccode = self._data.condition.get(CONDCODE)
            if ccode:
                conditions = self.hass.data.get(DATA_CONDITION)
                if conditions:
                    return conditions.get(ccode)

    @property
    def temperature(self):
        """Return the current temperature."""
        return self._data.temperature

    @property
    def pressure(self):
        """Return the current pressure."""
        return self._data.pressure

    @property
    def humidity(self):
        """Return the name of the sensor."""
        return self._data.humidity

    @property
    def visibility(self):
        """Return the current visibility."""
        return self._data.visibility

    @property
    def wind_speed(self):
        """Return the current windspeed."""
        return self._data.wind_speed

    @property
    def wind_bearing(self):
        """Return the current wind bearing (degrees)."""
        return self._data.wind_bearing

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def forecast(self):
        """Return the forecast array."""
        from buienradar.buienradar import (CONDITION, CONDCODE, DATETIME,
                                           MIN_TEMP, MAX_TEMP)

        if self._forecast:
            fcdata_out = []
            cond = self.hass.data[DATA_CONDITION]
            if self._data.forecast:
                for data_in in self._data.forecast:
                    # remap keys from external library to
                    # keys understood by the weather component:
                    data_out = {}
                    condcode = data_in.get(CONDITION, []).get(CONDCODE)

                    data_out[ATTR_FORECAST_TIME] = data_in.get(DATETIME)
                    data_out[ATTR_FORECAST_CONDITION] = cond[condcode]
                    data_out[ATTR_FORECAST_TEMP_LOW] = data_in.get(MIN_TEMP)
                    data_out[ATTR_FORECAST_TEMP] = data_in.get(MAX_TEMP)

                    fcdata_out.append(data_out)

            return fcdata_out
