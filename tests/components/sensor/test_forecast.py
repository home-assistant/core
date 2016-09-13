"""The tests for the forecast.io platform."""
import re
import unittest
from unittest.mock import MagicMock, patch

import forecastio
from requests.exceptions import HTTPError
import requests_mock

from homeassistant.components.sensor import forecast

from tests.common import load_fixture, get_test_home_assistant


class TestForecastSetup(unittest.TestCase):
    """Test the forecast.io platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.key = 'foo'
        self.config = {
            'api_key': 'foo',
            'monitored_conditions': ['summary', 'icon']
        }
        self.lat = 37.8267
        self.lon = -122.423
        self.hass.config.latitude = self.lat
        self.hass.config.longitude = self.lon

    def test_setup_no_latitude(self):
        """Test that the component is not loaded without required config."""
        self.hass.config.latitude = None
        self.assertFalse(forecast.setup_platform(self.hass, {}, MagicMock()))

    @patch('forecastio.api.get_forecast')
    def test_setup_bad_api_key(self, mock_get_forecast):
        """Test for handling a bad API key."""
        # The forecast API wrapper that we use raises an HTTP error
        # when you try to use a bad (or no) API key.
        url = 'https://api.forecast.io/forecast/{}/{},{}?units=auto'.format(
            self.key, str(self.lat), str(self.lon)
        )
        msg = '400 Client Error: Bad Request for url: {}'.format(url)
        mock_get_forecast.side_effect = HTTPError(msg,)

        response = forecast.setup_platform(self.hass, self.config, MagicMock())
        self.assertFalse(response)

    @requests_mock.Mocker()
    @patch('forecastio.api.get_forecast', wraps=forecastio.api.get_forecast)
    def test_setup(self, m, mock_get_forecast):
        """Test for successfully setting up the forecast.io platform."""
        uri = ('https://api.forecast.io\/forecast\/(\w+)\/'
               '(-?\d+\.?\d*),(-?\d+\.?\d*)')
        m.get(re.compile(uri),
              text=load_fixture('forecast.json'))
        forecast.setup_platform(self.hass, self.config, MagicMock())
        self.assertTrue(mock_get_forecast.called)
        self.assertEqual(mock_get_forecast.call_count, 1)
