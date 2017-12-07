"""
Support for the OpenWeatherMap (OWM) service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.openweathermap/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, TEMP_CELSIUS, TEMP_FAHRENHEIT,
    CONF_MONITORED_CONDITIONS, ATTR_ATTRIBUTION)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pyowm==2.7.1']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by OpenWeatherMap"
CONF_FORECAST = 'forecast'
CONF_LANGUAGE = 'language'

DEFAULT_NAME = 'OWM'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

SENSOR_TYPES = {
    'weather': ['Condition', None],
    'temperature': ['Temperature', None],
    'wind_speed': ['Wind speed', 'm/s'],
    'wind_bearing': ['Wind bearing', '°'],
    'humidity': ['Humidity', '%'],
    'pressure': ['Pressure', 'mbar'],
    'clouds': ['Cloud coverage', '%'],
    'rain': ['Rain', 'mm'],
    'snow': ['Snow', 'mm'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_FORECAST, default=False): cv.boolean,
    vol.Optional(CONF_LANGUAGE, default=None): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the OpenWeatherMap sensor."""
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    from pyowm import OWM

    SENSOR_TYPES['temperature'][1] = hass.config.units.temperature_unit

    name = config.get(CONF_NAME)
    forecast = config.get(CONF_FORECAST)
    language = config.get(CONF_LANGUAGE)
    if isinstance(language, str):
        language = language.lower()[:2]

    owm = OWM(API_key=config.get(CONF_API_KEY), language=language)

    if not owm:
        _LOGGER.error("Unable to connect to OpenWeatherMap")
        return False

    data = WeatherData(owm, forecast, hass.config.latitude,
                       hass.config.longitude)
    dev = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        dev.append(OpenWeatherMapSensor(
            name, data, variable, SENSOR_TYPES[variable][1]))

    if forecast:
        SENSOR_TYPES['forecast'] = ['Forecast', None]
        dev.append(OpenWeatherMapSensor(
            name, data, 'forecast', SENSOR_TYPES['temperature'][1]))

    add_devices(dev, True)


class OpenWeatherMapSensor(Entity):
    """Implementation of an OpenWeatherMap sensor."""

    def __init__(self, name, weather_data, sensor_type, temp_unit):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.owa_client = weather_data
        self.temp_unit = temp_unit
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    def update(self):
        """Get the latest data from OWM and updates the states."""
        from pyowm.exceptions.api_call_error import APICallError

        try:
            self.owa_client.update()
        except APICallError:
            _LOGGER.error("Exception when calling OWM web API to update data")
            return

        data = self.owa_client.data
        fc_data = self.owa_client.fc_data

        if data is None or fc_data is None:
            return

        if self.type == 'weather':
            self._state = data.get_detailed_status()
        elif self.type == 'temperature':
            if self.temp_unit == TEMP_CELSIUS:
                self._state = round(data.get_temperature('celsius')['temp'], 1)
            elif self.temp_unit == TEMP_FAHRENHEIT:
                self._state = round(data.get_temperature('fahrenheit')['temp'],
                                    1)
            else:
                self._state = round(data.get_temperature()['temp'], 1)
        elif self.type == 'wind_speed':
            self._state = round(data.get_wind()['speed'], 1)
        elif self.type == 'wind_bearing':
            self._state = round(data.get_wind()['deg'], 1)
        elif self.type == 'humidity':
            self._state = round(data.get_humidity(), 1)
        elif self.type == 'pressure':
            self._state = round(data.get_pressure()['press'], 0)
        elif self.type == 'clouds':
            self._state = data.get_clouds()
        elif self.type == 'rain':
            if data.get_rain():
                self._state = round(data.get_rain()['3h'], 0)
                self._unit_of_measurement = 'mm'
            else:
                self._state = 'not raining'
                self._unit_of_measurement = ''
        elif self.type == 'snow':
            if data.get_snow():
                self._state = round(data.get_snow(), 0)
                self._unit_of_measurement = 'mm'
            else:
                self._state = 'not snowing'
                self._unit_of_measurement = ''
        elif self.type == 'forecast':
            self._state = fc_data.get_weathers()[0].get_status()


class WeatherData(object):
    """Get the latest data from OpenWeatherMap."""

    def __init__(self, owm, forecast, latitude, longitude):
        """Initialize the data object."""
        self.owm = owm
        self.forecast = forecast
        self.latitude = latitude
        self.longitude = longitude
        self.data = None
        self.fc_data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from OpenWeatherMap."""
        from pyowm.exceptions.api_call_error import APICallError

        try:
            obs = self.owm.weather_at_coords(self.latitude, self.longitude)
        except (APICallError, TypeError):
            _LOGGER.error("Exception when calling OWM web API "
                          "to get weather at coords")
            obs = None

        if obs is None:
            _LOGGER.warning("Failed to fetch data")
            return

        self.data = obs.get_weather()

        if self.forecast == 1:
            try:
                obs = self.owm.three_hours_forecast_at_coords(
                    self.latitude, self.longitude)
                self.fc_data = obs.get_forecast()
            except (ConnectionResetError, TypeError):
                _LOGGER.warning("Failed to fetch forecast")
