"""The tests for the Dark Sky platform."""
import re
import unittest
from unittest.mock import MagicMock, patch
from datetime import timedelta

from requests.exceptions import HTTPError
import requests_mock

import forecastio

from homeassistant.components.sensor import darksky
from homeassistant.setup import setup_component

from tests.common import (load_fixture, get_test_home_assistant,
                          MockDependency)

VALID_CONFIG_MINIMAL = {
    'sensor': {
        'platform': 'darksky',
        'api_key': 'foo',
        'forecast': [1, 2],
        'monitored_conditions': ['summary', 'icon', 'temperature_max'],
        'update_interval': timedelta(seconds=120),
    }
}

INVALID_CONFIG_MINIMAL = {
    'sensor': {
        'platform': 'darksky',
        'api_key': 'foo',
        'forecast': [1, 2],
        'monitored_conditions': ['sumary', 'iocn', 'temperature_max'],
        'update_interval': timedelta(seconds=120),
    }
}

VALID_CONFIG_LANG_DE = {
    'sensor': {
        'platform': 'darksky',
        'api_key': 'foo',
        'forecast': [1, 2],
        'units': 'us',
        'language': 'de',
        'monitored_conditions': ['summary', 'icon', 'temperature_max',
                                 'minutely_summary', 'hourly_summary',
                                 'daily_summary', 'humidity', ],
        'update_interval': timedelta(seconds=120),
    }
}

INVALID_CONFIG_LANG = {
    'sensor': {
        'platform': 'darksky',
        'api_key': 'foo',
        'forecast': [1, 2],
        'language': 'yz',
        'monitored_conditions': ['summary', 'icon', 'temperature_max'],
        'update_interval': timedelta(seconds=120),
    }
}


def load_forecastMock(key, lat, lon,
                      units, lang):  # pylint: disable=invalid-name
    """Mock darksky forecast loading."""
    return ''


class TestDarkSkySetup(unittest.TestCase):
    """Test the Dark Sky platform."""

    def add_entities(self, new_entities, update_before_add=False):
        """Mock add entities."""
        if update_before_add:
            for entity in new_entities:
                entity.update()

        for entity in new_entities:
            self.entities.append(entity)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.key = 'foo'
        self.lat = self.hass.config.latitude = 37.8267
        self.lon = self.hass.config.longitude = -122.423
        self.entities = []

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @MockDependency('forecastio')
    @patch('forecastio.load_forecast', new=load_forecastMock)
    def test_setup_with_config(self, mock_forecastio):
        """Test the platform setup with configuration."""
        setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)

        state = self.hass.states.get('sensor.dark_sky_summary')
        assert state is not None

    @MockDependency('forecastio')
    @patch('forecastio.load_forecast', new=load_forecastMock)
    def test_setup_with_invalid_config(self, mock_forecastio):
        """Test the platform setup with invalid configuration."""
        setup_component(self.hass, 'sensor', INVALID_CONFIG_MINIMAL)

        state = self.hass.states.get('sensor.dark_sky_summary')
        assert state is None

    @MockDependency('forecastio')
    @patch('forecastio.load_forecast', new=load_forecastMock)
    def test_setup_with_language_config(self, mock_forecastio):
        """Test the platform setup with language configuration."""
        setup_component(self.hass, 'sensor', VALID_CONFIG_LANG_DE)

        state = self.hass.states.get('sensor.dark_sky_summary')
        assert state is not None

    @MockDependency('forecastio')
    @patch('forecastio.load_forecast', new=load_forecastMock)
    def test_setup_with_invalid_language_config(self, mock_forecastio):
        """Test the platform setup with language configuration."""
        setup_component(self.hass, 'sensor', INVALID_CONFIG_LANG)

        state = self.hass.states.get('sensor.dark_sky_summary')
        assert state is None

    @patch('forecastio.api.get_forecast')
    def test_setup_bad_api_key(self, mock_get_forecast):
        """Test for handling a bad API key."""
        # The Dark Sky API wrapper that we use raises an HTTP error
        # when you try to use a bad (or no) API key.
        url = 'https://api.darksky.net/forecast/{}/{},{}?units=auto'.format(
            self.key, str(self.lat), str(self.lon)
        )
        msg = '400 Client Error: Bad Request for url: {}'.format(url)
        mock_get_forecast.side_effect = HTTPError(msg,)

        response = darksky.setup_platform(self.hass, VALID_CONFIG_MINIMAL,
                                          MagicMock())
        self.assertFalse(response)

    @requests_mock.Mocker()
    @patch('forecastio.api.get_forecast', wraps=forecastio.api.get_forecast)
    def test_setup(self, mock_req, mock_get_forecast):
        """Test for successfully setting up the forecast.io platform."""
        uri = (r'https://api.(darksky.net|forecast.io)\/forecast\/(\w+)\/'
               r'(-?\d+\.?\d*),(-?\d+\.?\d*)')
        mock_req.get(re.compile(uri), text=load_fixture('darksky.json'))

        assert setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)

        self.assertTrue(mock_get_forecast.called)
        self.assertEqual(mock_get_forecast.call_count, 1)
        self.assertEqual(len(self.hass.states.entity_ids()), 7)

        state = self.hass.states.get('sensor.dark_sky_summary')
        assert state is not None
        self.assertEqual(state.state, 'Clear')
        self.assertEqual(state.attributes.get('friendly_name'),
                         'Dark Sky Summary')
