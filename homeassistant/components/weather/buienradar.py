"""
Support for Buienradar.nl weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.buienradar/
"""
import logging
import asyncio
from homeassistant.components.weather import (
    WeatherEntity, PLATFORM_SCHEMA)
from homeassistant.const import \
    CONF_NAME, TEMP_CELSIUS, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers import config_validation as cv
# Reuse data and API logic from the sensor implementation
from homeassistant.components.sensor.buienradar import (
    BrData)
import voluptuous as vol

REQUIREMENTS = ['buienradar==0.8']

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEFRAME = 60

CONF_FORECAST = 'forecast'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_FORECAST, default=True): cv.boolean,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
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
    async_add_devices([BrWeather(data, config.get(CONF_FORECAST, True),
                                 config.get(CONF_NAME, None))])

    # schedule the first update in 1 minute from now:
    yield from data.schedule_update(1)


class BrWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, data, forecast, stationname=None):
        """Initialise the platform with a data instance and station name."""
        self._stationname = stationname
        self._forecast = forecast
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
        """Return the name of the sensor."""
        return self._data.condition

    @property
    def temperature(self):
        """Return the name of the sensor."""
        return self._data.temperature

    @property
    def pressure(self):
        """Return the name of the sensor."""
        return self._data.pressure

    @property
    def humidity(self):
        """Return the name of the sensor."""
        return self._data.humidity

    @property
    def wind_speed(self):
        """Return the name of the sensor."""
        return self._data.wind_speed

    @property
    def wind_bearing(self):
        """Return the name of the sensor."""
        return self._data.wind_bearing

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def forecast(self):
        """Return the forecast."""
        if self._forecast:
            return self._data.forecast
