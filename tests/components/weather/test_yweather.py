"""The tests for the Yahoo weather component."""
import json

import unittest
import requests_mock
from unittest.mock import patch, MagicMock

#from homeassistant.components import weather
from homeassistant.components.weather import yweather
from homeassistant.components.weather import (
    ATTR_WEATHER_ATTRIBUTION, ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRESSURE, ATTR_WEATHER_TEMPERATURE, ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED, ATTR_FORECAST, ATTR_FORECAST_TEMP)
from homeassistant.util.unit_system import METRIC_SYSTEM
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, load_fixture


def mock_responses(mock):
    """Mock responses for Yahoo Weather."""
    base_url = 'https://query.yahooapis.com/v1/public/yql'
    mock.get(base_url +
             '?q=SELECT+woeid+FROM+geo.places+WHERE+text+%3D+%27%2832.87336'+
             '%2C-117.22743%29%27&format=json',
             text=load_fixture('yahooweather.json'))

def _yql_queryMock(yql):
    """Mock yahoo query language query."""
    return ('{"query": {"count": 1, "created": "2017-11-17T13:40:47Z", '
            '"lang": "en-US", "results": {"place": {"woeid": "23511632"}}}}')

def get_woeidMock(lat, lon):
    """Mock get woeid Where On Earth Identifiers."""
    return '23511632'

class YahooWeatherMock():
    """Mock class for the YahooWeather object."""

    def __init__(self, woeid, temp_unit):
        """Initialize Telnet object."""
        self.woeid = woeid
        self.temp_unit = temp_unit
        self._data = json.loads(load_fixture('yahooweather.json'))

    def updateWeather(self):
        """Return sample values."""
        return True

    @property
    def RawData(self):
        """Raw Data."""
        if self.woeid == '12345':
            return json.loads('[]')
        return self._data

    @property
    def Now(self):
        """Current weather data."""
        if self.woeid == '111':
            raise ValueError
            return None
        return self._data['query']['results']['channel']['item']['condition']

    @property
    def Atmosphere(self):
        """Atmosphere weather data."""
        return self._data['query']['results']['channel']['atmosphere']

    @property
    def Wind(self):
        """Wind weather data."""
        return self._data['query']['results']['channel']['wind']

    @property
    def Forecast(self):
        """Forecast data 0-5 Days."""
        if self.woeid == '123123':
            raise ValueError
        else:
            return self._data['query']['results']['channel']['item']['forecast']
        return None


class TestWeather(unittest.TestCase):
    """Test the Yahoo weather component."""

    DEVICES = []

    @requests_mock.Mocker()
    def add_devices(self, devices, mock):
        """Mock add devices."""
        mock_responses(mock)
        for device in devices:
            device.update()
            self.DEVICES.append(device)

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    @requests_mock.Mocker()
    def test_setup(self, mock):
        """Test for typical weather data attributes."""
        mock_responses(mock)
        self.assertTrue(
            setup_component(self.hass, 'weather', {
                'weather': {
                    'platform': 'yweather',
                    }
                }))

        state = self.hass.states.get('weather.yweather')
        assert state is not None

        assert state.state == 'cloudy'

        data = state.attributes
        self.assertEqual(data.get(ATTR_WEATHER_TEMPERATURE), 18.0)
        self.assertEqual(data.get(ATTR_WEATHER_HUMIDITY), 71)
        self.assertEqual(data.get(ATTR_WEATHER_PRESSURE), 34100.95)
        self.assertEqual(data.get(ATTR_WEATHER_WIND_SPEED), 6.44)
        self.assertEqual(data.get(ATTR_WEATHER_WIND_BEARING), 0)
        self.assertEqual(state.attributes.get('friendly_name'), 'Yweather')

    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    @requests_mock.Mocker()
    def test_setup_no_data(self, mock):
        """Test for note receiving data."""
        mock_responses(mock)
        self.assertTrue(
            setup_component(self.hass, 'weather', {
                'weather': {
                    'platform': 'yweather',
                    'woeid': '12345',
                    }
                }))

        state = self.hass.states.get('weather.yweather')
        assert state is not None

    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    @requests_mock.Mocker()
    def test_setup_bad_data(self, mock):
        """Test for bad forecast data."""
        mock_responses(mock)
        self.assertTrue(
            setup_component(self.hass, 'weather', {
                'weather': {
                    'platform': 'yweather',
                    'woeid': '123123',
                    }
                }))

        state = self.hass.states.get('weather.yweather')
        assert state is None

    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    @requests_mock.Mocker()
    def test_setup_condition_error(self, mock):
        """Test for bad forecast data."""
        mock_responses(mock)
        self.assertTrue(
            setup_component(self.hass, 'weather', {
                'weather': {
                    'platform': 'yweather',
                    'woeid': '111',
                    }
                }))

        state = self.hass.states.get('weather.yweather')
        assert state is None
