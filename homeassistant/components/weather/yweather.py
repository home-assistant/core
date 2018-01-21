"""
Support for the Yahoo! Weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.yweather/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_TEMP, ATTR_FORECAST_TIME, PLATFORM_SCHEMA, WeatherEntity)
from homeassistant.const import CONF_NAME, STATE_UNKNOWN, TEMP_CELSIUS
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ["yahooweather==0.10"]

_LOGGER = logging.getLogger(__name__)

DATA_CONDITION = 'yahoo_condition'

ATTR_FORECAST_CONDITION = 'condition'
ATTRIBUTION = "Weather details provided by Yahoo! Inc."

ATTR_FORECAST_TEMP_LOW = 'templow'

CONF_WOEID = 'woeid'

DEFAULT_NAME = 'Yweather'

SCAN_INTERVAL = timedelta(minutes=10)

CONDITION_CLASSES = {
    'cloudy': [26, 27, 28, 29, 30],
    'fog': [19, 20, 21, 22, 23],
    'hail': [17, 18, 35],
    'lightning': [37],
    'lightning-rainy': [3, 4, 38, 39, 47],
    'partlycloudy': [44],
    'pouring': [40, 45],
    'rainy': [9, 11, 12],
    'snowy': [8, 13, 14, 15, 16, 41, 42, 43],
    'snowy-rainy': [5, 6, 7, 10, 46],
    'sunny': [32, 33, 34, 25, 36],
    'windy': [24],
    'windy-variant': [],
    'exceptional': [0, 1, 2],
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_WOEID, default=None): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Yahoo! weather platform."""
    from yahooweather import get_woeid, UNIT_C, UNIT_F

    unit = hass.config.units.temperature_unit
    woeid = config.get(CONF_WOEID)
    name = config.get(CONF_NAME)

    yunit = UNIT_C if unit == TEMP_CELSIUS else UNIT_F

    # If not exists a customer WOEID/calculation from Home Assistant
    if woeid is None:
        woeid = get_woeid(hass.config.latitude, hass.config.longitude)
        if woeid is None:
            _LOGGER.warning("Can't retrieve WOEID from Yahoo!")
            return False

    yahoo_api = YahooWeatherData(woeid, yunit)

    if not yahoo_api.update():
        _LOGGER.critical("Can't retrieve weather data from Yahoo!")
        return False

    # create condition helper
    if DATA_CONDITION not in hass.data:
        hass.data[DATA_CONDITION] = [str(x) for x in range(0, 50)]
        for cond, condlst in CONDITION_CLASSES.items():
            for condi in condlst:
                hass.data[DATA_CONDITION][condi] = cond

    add_devices([YahooWeatherWeather(yahoo_api, name, unit)], True)


class YahooWeatherWeather(WeatherEntity):
    """Representation of Yahoo! weather data."""

    def __init__(self, weather_data, name, unit):
        """Initialize the sensor."""
        self._name = name
        self._data = weather_data
        self._unit = unit

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        try:
            return self.hass.data[DATA_CONDITION][int(
                self._data.yahoo.Now['code'])]
        except (ValueError, IndexError):
            return STATE_UNKNOWN

    @property
    def temperature(self):
        """Return the temperature."""
        return int(self._data.yahoo.Now['temp'])

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def pressure(self):
        """Return the pressure."""
        return round(float(self._data.yahoo.Atmosphere['pressure'])/33.8637526,
                     2)

    @property
    def humidity(self):
        """Return the humidity."""
        return int(self._data.yahoo.Atmosphere['humidity'])

    @property
    def visibility(self):
        """Return the visibility."""
        return round(float(self._data.yahoo.Atmosphere['visibility'])/1.61, 2)

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return round(float(self._data.yahoo.Wind['speed'])/1.61, 2)

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return int(self._data.yahoo.Wind['direction'])

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        try:
            return [
                {
                    ATTR_FORECAST_TIME: v['date'],
                    ATTR_FORECAST_TEMP:int(v['high']),
                    ATTR_FORECAST_TEMP_LOW: int(v['low']),
                    ATTR_FORECAST_CONDITION:
                        self.hass.data[DATA_CONDITION][int(v['code'])]
                } for v in self._data.yahoo.Forecast]
        except (ValueError, IndexError):
            return STATE_UNKNOWN

    def update(self):
        """Get the latest data from Yahoo! and updates the states."""
        self._data.update()
        if not self._data.yahoo.RawData:
            _LOGGER.info("Don't receive weather data from Yahoo!")
            return


class YahooWeatherData(object):
    """Handle the Yahoo! API object and limit updates."""

    def __init__(self, woeid, temp_unit):
        """Initialize the data object."""
        from yahooweather import YahooWeather
        self._yahoo = YahooWeather(woeid, temp_unit)

    @property
    def yahoo(self):
        """Return Yahoo! API object."""
        return self._yahoo

    def update(self):
        """Get the latest data from Yahoo!."""
        return self._yahoo.updateWeather()
