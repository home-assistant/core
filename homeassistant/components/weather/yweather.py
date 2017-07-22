"""
Support for the Yahoo! Weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.yweather/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.weather import (
    WeatherEntity, PLATFORM_SCHEMA, ATTR_FORECAST_TEMP)
from homeassistant.const import (TEMP_CELSIUS, CONF_NAME, STATE_UNKNOWN)

REQUIREMENTS = ["yahooweather==0.8"]

_LOGGER = logging.getLogger(__name__)

ATTR_FORECAST_CONDITION = 'condition'
ATTRIBUTION = "Weather details provided by Yahoo! Inc."

CONF_FORECAST = 'forecast'
CONF_WOEID = 'woeid'

DEFAULT_NAME = 'Yweather'

SCAN_INTERVAL = timedelta(minutes=10)

CONDITION_CLASSES = {
    'cloudy': [26, 27, 28, 29, 30],
    'fog': [19, 20, 21, 22, 23],
    'hail': [17, 18, 35],
    'lightning': [37],
    'lightning-rainy': [38, 39],
    'partlycloudy': [44],
    'pouring': [40, 45],
    'rainy': [9, 11, 12],
    'snowy': [8, 13, 14, 15, 16, 41, 42, 43],
    'snowy-rainy': [5, 6, 7, 10, 46, 47],
    'sunny': [32],
    'windy': [24],
    'windy-variant': [],
    'exceptional': [0, 1, 2, 3, 4, 25, 36],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_WOEID, default=None): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_FORECAST, default=0):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Yahoo! weather platform."""
    from yahooweather import get_woeid, UNIT_C, UNIT_F

    unit = hass.config.units.temperature_unit
    woeid = config.get(CONF_WOEID)
    forecast = config.get(CONF_FORECAST)
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

    if forecast >= len(yahoo_api.yahoo.Forecast):
        _LOGGER.error("Yahoo! only support %d days forecast",
                      len(yahoo_api.yahoo.Forecast))
        return False

    add_devices([YahooWeatherWeather(yahoo_api, name, forecast)], True)


class YahooWeatherWeather(WeatherEntity):
    """Representation of Yahoo! weather data."""

    def __init__(self, weather_data, name, forecast):
        """Initialize the sensor."""
        self._name = name
        self._data = weather_data
        self._forecast = forecast

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        try:
            return [k for k, v in CONDITION_CLASSES.items() if
                    int(self._data.yahoo.Now['code']) in v][0]
        except IndexError:
            return STATE_UNKNOWN

    @property
    def temperature(self):
        """Return the temperature."""
        return self._data.yahoo.Now['temp']

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        return self._data.yahoo.Atmosphere['pressure']

    @property
    def humidity(self):
        """Return the humidity."""
        return self._data.yahoo.Atmosphere['humidity']

    @property
    def visibility(self):
        """Return the visibility."""
        return self._data.yahoo.Atmosphere['visibility']

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._data.yahoo.Wind['speed']

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        try:
            forecast_condition = \
                [k for k, v in CONDITION_CLASSES.items() if
                 int(self._data.yahoo.Forecast[self._forecast]['code'])
                 in v][0]
        except IndexError:
            return STATE_UNKNOWN

        return [{
            ATTR_FORECAST_CONDITION: forecast_condition,
            ATTR_FORECAST_TEMP:
                self._data.yahoo.Forecast[self._forecast]['high'],
        }]

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
