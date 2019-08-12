"""The tests for the Yahoo weather component."""
import json

import unittest
from unittest.mock import patch

from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_PRESSURE, ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING, ATTR_WEATHER_WIND_SPEED)
from homeassistant.util.unit_system import METRIC_SYSTEM
from homeassistant.setup import setup_component

from tests.common import (get_test_home_assistant, load_fixture,
                          MockDependency)


def _yql_queryMock(yql):  # pylint: disable=invalid-name
    """Mock yahoo query language query."""
    return ('{"query": {"count": 1, "created": "2017-11-17T13:40:47Z", '
            '"lang": "en-US", "results": {"place": {"woeid": "23511632"}}}}')


def get_woeidMock(lat, lon):  # pylint: disable=invalid-name
    """Mock get woeid Where On Earth Identifiers."""
    return '23511632'


class YahooWeatherMock():
    """Mock class for the YahooWeather object."""

    def __init__(self, woeid, temp_unit):
        """Initialize Telnet object."""
        self.woeid = woeid
        self.temp_unit = temp_unit
        self._data = json.loads(load_fixture('yahooweather.json'))

    # pylint: disable=no-self-use
    def updateWeather(self):  # pylint: disable=invalid-name
        """Return sample values."""
        return True

    @property
    def RawData(self):  # pylint: disable=invalid-name
        """Return raw Data."""
        if self.woeid == '12345':
            return json.loads('[]')
        return self._data

    @property
    def Now(self):  # pylint: disable=invalid-name
        """Return current weather data."""
        if self.woeid == '111':
            raise ValueError
        return self._data['query']['results']['channel']['item']['condition']

    @property
    def Atmosphere(self):  # pylint: disable=invalid-name
        """Return atmosphere weather data."""
        return self._data['query']['results']['channel']['atmosphere']

    @property
    def Wind(self):  # pylint: disable=invalid-name
        """Return wind weather data."""
        return self._data['query']['results']['channel']['wind']

    @property
    def Forecast(self):  # pylint: disable=invalid-name
        """Return forecast data 0-5 Days."""
        if self.woeid == '123123':
            raise ValueError
        return self._data['query']['results']['channel']['item']['forecast']


class TestWeather(unittest.TestCase):
    """Test the Yahoo weather component."""

    DEVICES = []

    def add_entities(self, devices):
        """Mock add devices."""
        for device in devices:
            device.update()
            self.DEVICES.append(device)

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @MockDependency('yahooweather')
    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    def test_setup(self, mock_yahooweather):
        """Test for typical weather data attributes."""
        assert setup_component(self.hass, 'weather', {
                'weather': {
                    'platform': 'yweather',
                    }
                })

        state = self.hass.states.get('weather.yweather')
        assert state is not None

        assert state.state == 'cloudy'

        data = state.attributes
        assert data.get(ATTR_WEATHER_TEMPERATURE) == 18.0
        assert data.get(ATTR_WEATHER_HUMIDITY) == 71
        assert data.get(ATTR_WEATHER_PRESSURE) == 1000.0
        assert data.get(ATTR_WEATHER_WIND_SPEED) == 3.94
        assert data.get(ATTR_WEATHER_WIND_BEARING) == 0
        assert state.attributes.get('friendly_name') == 'Yweather'

    @MockDependency('yahooweather')
    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    def test_setup_no_data(self, mock_yahooweather):
        """Test for note receiving data."""
        assert setup_component(self.hass, 'weather', {
                'weather': {
                    'platform': 'yweather',
                    'woeid': '12345',
                    }
                })

        state = self.hass.states.get('weather.yweather')
        assert state is not None

    @MockDependency('yahooweather')
    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    def test_setup_bad_data(self, mock_yahooweather):
        """Test for bad forecast data."""
        assert setup_component(self.hass, 'weather', {
                'weather': {
                    'platform': 'yweather',
                    'woeid': '123123',
                    }
                })

        state = self.hass.states.get('weather.yweather')
        assert state is None

    @MockDependency('yahooweather')
    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    def test_setup_condition_error(self, mock_yahooweather):
        """Test for bad forecast data."""
        assert setup_component(self.hass, 'weather', {
                'weather': {
                    'platform': 'yweather',
                    'woeid': '111',
                    }
                })

        state = self.hass.states.get('weather.yweather')
        assert state is None
