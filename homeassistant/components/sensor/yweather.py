"""
Support for the Yahoo! Weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.yweather/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    TEMP_CELSIUS, CONF_MONITORED_CONDITIONS, CONF_NAME,
    ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['yahooweather==0.10']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Weather details provided by Yahoo! Inc."

CONF_FORECAST = 'forecast'
CONF_WOEID = 'woeid'

DEFAULT_NAME = 'Yweather'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

SENSOR_TYPES = {
    'weather_current': ['Current', None],
    'weather': ['Condition', None],
    'temperature': ['Temperature', 'temperature'],
    'temp_min': ['Temperature min', 'temperature'],
    'temp_max': ['Temperature max', 'temperature'],
    'wind_speed': ['Wind speed', 'speed'],
    'humidity': ['Humidity', '%'],
    'pressure': ['Pressure', 'pressure'],
    'visibility': ['Visibility', 'distance'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_WOEID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_FORECAST, default=0):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        [vol.In(SENSOR_TYPES)],
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Yahoo! weather sensor."""
    from yahooweather import get_woeid, UNIT_C, UNIT_F

    unit = hass.config.units.temperature_unit
    woeid = config.get(CONF_WOEID)
    forecast = config.get(CONF_FORECAST)
    name = config.get(CONF_NAME)

    yunit = UNIT_C if unit == TEMP_CELSIUS else UNIT_F

    SENSOR_TYPES['temperature'][1] = unit
    SENSOR_TYPES['temp_min'][1] = unit
    SENSOR_TYPES['temp_max'][1] = unit

    # If not exists a customer WOEID/calculation from Home Assistant
    if woeid is None:
        woeid = get_woeid(hass.config.latitude, hass.config.longitude)
        if woeid is None:
            _LOGGER.critical("Can't retrieve WOEID from yahoo!")
            return False

    yahoo_api = YahooWeatherData(woeid, yunit)

    if not yahoo_api.update():
        _LOGGER.critical("Can't retrieve weather data from Yahoo!")
        return False

    if forecast >= len(yahoo_api.yahoo.Forecast):
        _LOGGER.error("Yahoo! only support %d days forecast!",
                      len(yahoo_api.yahoo.Forecast))
        return False

    dev = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        dev.append(YahooWeatherSensor(yahoo_api, name, forecast, variable))

    add_entities(dev, True)


class YahooWeatherSensor(Entity):
    """Implementation of the Yahoo! weather sensor."""

    def __init__(self, weather_data, name, forecast, sensor_type):
        """Initialize the sensor."""
        self._client = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self._type = sensor_type
        self._state = None
        self._unit = SENSOR_TYPES[sensor_type][1]
        self._data = weather_data
        self._forecast = forecast
        self._code = None

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
        return self._data.yahoo.Units.get(self._unit, self._unit)

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        if self._code is None or "weather" not in self._type:
            return None

        return self._data.yahoo.getWeatherImage(self._code)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

        if self._code is not None and "weather" in self._type:
            attrs['condition_code'] = self._code

        return attrs

    def update(self):
        """Get the latest data from Yahoo! and updates the states."""
        self._data.update()
        if not self._data.yahoo.RawData:
            _LOGGER.info("Don't receive weather data from Yahoo!")
            return

        # Default code for weather image
        self._code = self._data.yahoo.Now['code']

        # Read data
        if self._type == 'weather_current':
            self._state = self._data.yahoo.Now['text']
        elif self._type == 'weather':
            self._code = self._data.yahoo.Forecast[self._forecast]['code']
            self._state = self._data.yahoo.Forecast[self._forecast]['text']
        elif self._type == 'temperature':
            self._state = self._data.yahoo.Now['temp']
        elif self._type == 'temp_min':
            self._code = self._data.yahoo.Forecast[self._forecast]['code']
            self._state = self._data.yahoo.Forecast[self._forecast]['low']
        elif self._type == 'temp_max':
            self._code = self._data.yahoo.Forecast[self._forecast]['code']
            self._state = self._data.yahoo.Forecast[self._forecast]['high']
        elif self._type == 'wind_speed':
            self._state = round(float(self._data.yahoo.Wind['speed'])/1.61, 2)
        elif self._type == 'humidity':
            self._state = self._data.yahoo.Atmosphere['humidity']
        elif self._type == 'pressure':
            self._state = round(
                float(self._data.yahoo.Atmosphere['pressure'])/33.8637526, 2)
        elif self._type == 'visibility':
            self._state = round(
                float(self._data.yahoo.Atmosphere['visibility'])/1.61, 2)


class YahooWeatherData:
    """Handle Yahoo! API object and limit updates."""

    def __init__(self, woeid, temp_unit):
        """Initialize the data object."""
        from yahooweather import YahooWeather
        self._yahoo = YahooWeather(woeid, temp_unit)

    @property
    def yahoo(self):
        """Return Yahoo! API object."""
        return self._yahoo

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Yahoo!."""
        return self._yahoo.updateWeather()
