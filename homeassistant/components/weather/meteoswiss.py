"""
Support for MeteoSwiss.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.meteoswiss/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION, ATTR_FORECAST_TEMP, ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME, ATTR_FORECAST_PRECIPITATION, PLATFORM_SCHEMA,
    WeatherEntity)
from homeassistant.const import CONF_NAME, STATE_UNKNOWN, TEMP_CELSIUS
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DATA_CONDITION = 'meteoswiss_condition'

ATTRIBUTION = "Data provided by MeteoSwiss"


CONF_POSTAL_CODE = 'postal_code'

DEFAULT_NAME = 'MeteoSwiss'
API_URL = 'https://app-prod-ws.meteoswiss-app.ch/v1/plzDetail?plz={}'

SCAN_INTERVAL = timedelta(minutes=10)

CONDITION_CLASSES = {
    'clear-night': [101, 102, 126],
    'cloudy': [5, 105, 35, 135],
    'fog': [27, 127, 28, 128],
    'hail': [],
    'lightning': [12, 112],
    'lightning-rainy': [13, 113, 23, 123, 24, 124, 25, 125],
    'partlycloudy': [3, 103, 4, 104],
    'pouring': [17, 117, 20, 120, 33, 133],
    'rainy': [6, 106, 9, 109, 14, 114, 29, 129, 32, 132],
    'snowy': [8, 108, 11, 111, 16, 116, 19, 119, 22, 122, 30, 130, 34, 134],
    'snowy-rainy': [7, 107, 10, 110, 15, 115, 18, 118, 21, 121, 31, 131],
    'sunny': [1, 2, 26],
    'windy': [],
    'windy-variant': [],
    'exceptional': [],
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_POSTAL_CODE): vol.Range(min=1000, max=999999),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the MeteoSwiss platform."""
    postal_code = str(config.get(CONF_POSTAL_CODE))
    if len(postal_code) == 4:
        postal_code = postal_code + "00"
    name = config.get(CONF_NAME)

    meteoswiss_api = MeteoSwissData(postal_code)

    if not meteoswiss_api.update():
        _LOGGER.critical("Can't retrieve weather data from MeteoSwiss")
        return False

    # create condition helper
    if DATA_CONDITION not in hass.data:
        hass.data[DATA_CONDITION] = [str(x) for x in range(0, 200)]
        for cond, condlst in CONDITION_CLASSES.items():
            for condi in condlst:
                hass.data[DATA_CONDITION][condi] = cond

    add_entities([MeteoSwissWeather(meteoswiss_api, name)], True)


class MeteoSwissWeather(WeatherEntity):
    """Representation of MeteoSwiss data."""

    def __init__(self, weather_data, name):
        """Initialize the sensor."""
        self._name = name
        self._data = weather_data

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        try:
            return self.hass.data[DATA_CONDITION][int(
                self._data.meteoswiss['currentWeather']['icon'])]
        except (ValueError, IndexError):
            return STATE_UNKNOWN

    @property
    def temperature(self):
        """Return the temperature."""
        return float(self._data.meteoswiss['currentWeather']['temperature'])

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        return None

    @property
    def humidity(self):
        """Return the humidity."""
        return None

    @property
    def visibility(self):
        """Return the visibility."""
        return None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return None

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return None

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
                    ATTR_FORECAST_TIME: v['dayDate'],
                    ATTR_FORECAST_TEMP:int(v['temperatureMax']),
                    ATTR_FORECAST_TEMP_LOW: int(v['temperatureMin']),
                    ATTR_FORECAST_PRECIPITATION: float(v['precipitation']),
                    ATTR_FORECAST_CONDITION:
                        self.hass.data[DATA_CONDITION][int(v['iconDay'])]
                } for v in self._data.meteoswiss['forecast']]
        except (ValueError, IndexError):
            return STATE_UNKNOWN

    def update(self):
        """Get the latest data from MeteoSwiss and updates the states."""
        self._data.update()
        if not self._data.meteoswiss:
            _LOGGER.info("Don't receive weather data from MeteoSwiss")
            return


class MeteoSwissData:
    """Handle the calls to MeteoSwiss API."""

    def __init__(self, postal_code):
        """Initialize the data object."""
        self._meteoswiss = None
        self._postal_code = postal_code

    @property
    def meteoswiss(self):
        """Return MeteoSwiss API object."""
        return self._meteoswiss

    def update(self):
        """Get the latest data from MeteoSwiss."""
        import requests
        url = API_URL.format(self._postal_code)
        request = requests.get(url)
        if request.ok:
            self._meteoswiss = request.json()
            return True
        return False
