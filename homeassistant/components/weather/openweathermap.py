"""
Support for the OpenWeatherMap (OWM) service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.openweathermap/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.weather import WeatherEntity, PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['pyowm==2.5.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'OpenWeatherMap'
ATTRIBUTION = 'Data provided by OpenWeatherMap'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

CONDITION_CLASSES = {
    'cloudy': [804],
    'fog': [701, 741],
    'hail': [906],
    'lightning': [210, 211, 212, 221],
    'lightning-rainy': [200, 201, 202, 230, 231, 232],
    'partlycloudy': [801, 802, 803],
    'pouring': [504, 314, 502, 503, 522],
    'rainy': [300, 301, 302, 310, 311, 312, 313, 500, 501, 520, 521],
    'snowy': [600, 601, 602, 611, 612, 620, 621, 622],
    'snowy-rainy': [511, 615, 616],
    'sunny': [800],
    'windy': [905, 951, 952, 953, 954, 955, 956, 957],
    'windy-variant': [958, 959, 960, 961],
    'exceptional': [711, 721, 731, 751, 761, 762, 771, 900, 901, 962, 903,
                    904],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the OpenWeatherMap weather platform."""
    import pyowm

    longitude = config.get(CONF_LONGITUDE, round(hass.config.longitude, 5))
    latitude = config.get(CONF_LATITUDE, round(hass.config.latitude, 5))
    name = config.get(CONF_NAME)

    try:
        owm = pyowm.OWM(config.get(CONF_API_KEY))
    except pyowm.exceptions.api_call_error.APICallError:
        _LOGGER.error("Error while connecting to OpenWeatherMap")
        return False

    data = WeatherData(owm, latitude, longitude)

    add_devices([OpenWeatherMapWeather(
        name, data, hass.config.units.temperature_unit)], True)


class OpenWeatherMapWeather(WeatherEntity):
    """Implementation of an OpenWeatherMap sensor."""

    def __init__(self, name, owm, temperature_unit):
        """Initialize the sensor."""
        self._name = name
        self._owm = owm
        self._temperature_unit = temperature_unit
        self.data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        try:
            return [k for k, v in CONDITION_CLASSES.items() if
                    self.data.get_weather_code() in v][0]
        except IndexError:
            return STATE_UNKNOWN

    @property
    def temperature(self):
        """Return the temperature."""
        return self.data.get_temperature('celsius').get('temp')

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._temperature_unit

    @property
    def pressure(self):
        """Return the pressure."""
        return self.data.get_pressure().get('press')

    @property
    def humidity(self):
        """Return the humidity."""
        return self.data.get_humidity()

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self.data.get_wind().get('speed')

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.data.get_wind().get('deg')

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    def update(self):
        """Get the latest data from OWM and updates the states."""
        self._owm.update()
        self.data = self._owm.data


class WeatherData(object):
    """Get the latest data from OpenWeatherMap."""

    def __init__(self, owm, latitude, longitude):
        """Initialize the data object."""
        self.owm = owm
        self.latitude = latitude
        self.longitude = longitude
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from OpenWeatherMap."""
        obs = self.owm.weather_at_coords(self.latitude, self.longitude)
        if obs is None:
            _LOGGER.warning("Failed to fetch data from OWM")
            return

        self.data = obs.get_weather()
