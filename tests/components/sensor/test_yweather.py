"""The tests for the Yahoo weather sensor component."""
import json

import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component

from tests.common import (get_test_home_assistant, load_fixture,
                          MockDependency)

VALID_CONFIG_MINIMAL = {
    'sensor': {
        'platform': 'yweather',
        'monitored_conditions': [
            'weather',
            ],
    }
}

VALID_CONFIG_ALL = {
    'sensor': {
        'platform': 'yweather',
        'monitored_conditions': [
            'weather',
            'weather_current',
            'temperature',
            'temp_min',
            'temp_max',
            'wind_speed',
            'pressure',
            'visibility',
            'humidity',
        ],
    }
}

BAD_CONF_RAW = {
    'sensor': {
        'platform': 'yweather',
        'woeid': '12345',
        'monitored_conditions': [
            'weather',
        ],
    }
}

BAD_CONF_DATA = {
    'sensor': {
        'platform': 'yweather',
        'woeid': '111',
        'monitored_conditions': [
            'weather',
        ],
    }
}


def _yql_queryMock(yql):  # pylint: disable=invalid-name
    """Mock yahoo query language query."""
    return ('{"query": {"count": 1, "created": "2017-11-17T13:40:47Z", '
            '"lang": "en-US", "results": {"place": {"woeid": "23511632"}}}}')


def get_woeidMock(lat, lon):  # pylint: disable=invalid-name
    """Mock get woeid Where On Earth Identifiers."""
    return '23511632'


def get_woeidNoneMock(lat, lon):  # pylint: disable=invalid-name
    """Mock get woeid Where On Earth Identifiers."""
    return None


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
        """Raw Data."""
        if self.woeid == '12345':
            return json.loads('[]')
        return self._data

    @property
    def Units(self):  # pylint: disable=invalid-name
        """Return dict with units."""
        return self._data['query']['results']['channel']['units']

    @property
    def Now(self):  # pylint: disable=invalid-name
        """Current weather data."""
        if self.woeid == '111':
            raise ValueError
        return self._data['query']['results']['channel']['item']['condition']

    @property
    def Atmosphere(self):  # pylint: disable=invalid-name
        """Atmosphere weather data."""
        return self._data['query']['results']['channel']['atmosphere']

    @property
    def Wind(self):  # pylint: disable=invalid-name
        """Wind weather data."""
        return self._data['query']['results']['channel']['wind']

    @property
    def Forecast(self):  # pylint: disable=invalid-name
        """Forecast data 0-5 Days."""
        return self._data['query']['results']['channel']['item']['forecast']

    def getWeatherImage(self, code):  # pylint: disable=invalid-name
        """Create a link to weather image from yahoo code."""
        return "https://l.yimg.com/a/i/us/we/52/{}.gif".format(code)


class TestWeather(unittest.TestCase):
    """Test the Yahoo weather component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @MockDependency('yahooweather')
    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    def test_setup_minimal(self, mock_yahooweather):
        """Test for minimal weather sensor config."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)

        state = self.hass.states.get('sensor.yweather_condition')
        assert state is not None

        assert state.state == 'Mostly Cloudy'
        self.assertEqual(state.attributes.get('friendly_name'),
                         'Yweather Condition')

    @MockDependency('yahooweather')
    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    def test_setup_all(self, mock_yahooweather):
        """Test for all weather data attributes."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_ALL)

        state = self.hass.states.get('sensor.yweather_condition')
        assert state is not None
        self.assertEqual(state.state, 'Mostly Cloudy')
        self.assertEqual(state.attributes.get('condition_code'),
                         '28')
        self.assertEqual(state.attributes.get('friendly_name'),
                         'Yweather Condition')

        state = self.hass.states.get('sensor.yweather_current')
        assert state is not None
        self.assertEqual(state.state, 'Cloudy')
        self.assertEqual(state.attributes.get('friendly_name'),
                         'Yweather Current')

        state = self.hass.states.get('sensor.yweather_temperature')
        assert state is not None
        self.assertEqual(state.state, '18')
        self.assertEqual(state.attributes.get('friendly_name'),
                         'Yweather Temperature')

        state = self.hass.states.get('sensor.yweather_temperature_max')
        assert state is not None
        self.assertEqual(state.state, '23')
        self.assertEqual(state.attributes.get('friendly_name'),
                         'Yweather Temperature max')

        state = self.hass.states.get('sensor.yweather_temperature_min')
        assert state is not None
        self.assertEqual(state.state, '16')
        self.assertEqual(state.attributes.get('friendly_name'),
                         'Yweather Temperature min')

        state = self.hass.states.get('sensor.yweather_wind_speed')
        assert state is not None
        self.assertEqual(state.state, '3.94')
        self.assertEqual(state.attributes.get('friendly_name'),
                         'Yweather Wind speed')

        state = self.hass.states.get('sensor.yweather_pressure')
        assert state is not None
        self.assertEqual(state.state, '1000.0')
        self.assertEqual(state.attributes.get('friendly_name'),
                         'Yweather Pressure')

        state = self.hass.states.get('sensor.yweather_visibility')
        assert state is not None
        self.assertEqual(state.state, '14.23')
        self.assertEqual(state.attributes.get('friendly_name'),
                         'Yweather Visibility')

        state = self.hass.states.get('sensor.yweather_humidity')
        assert state is not None
        self.assertEqual(state.state, '71')
        self.assertEqual(state.attributes.get('friendly_name'),
                         'Yweather Humidity')

    @MockDependency('yahooweather')
    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidNoneMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    def test_setup_bad_woied(self, mock_yahooweather):
        """Test for bad woeid."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)

        state = self.hass.states.get('sensor.yweather_condition')
        assert state is None

    @MockDependency('yahooweather')
    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    def test_setup_bad_raw(self, mock_yahooweather):
        """Test for bad RawData."""
        assert setup_component(self.hass, 'sensor', BAD_CONF_RAW)

        state = self.hass.states.get('sensor.yweather_condition')
        assert state is not None

    @MockDependency('yahooweather')
    @patch('yahooweather._yql_query', new=_yql_queryMock)
    @patch('yahooweather.get_woeid', new=get_woeidMock)
    @patch('yahooweather.YahooWeather', new=YahooWeatherMock)
    def test_setup_bad_data(self, mock_yahooweather):
        """Test for bad data."""
        assert setup_component(self.hass, 'sensor', BAD_CONF_DATA)

        state = self.hass.states.get('sensor.yweather_condition')
        assert state is None
