"""The tests for the Dark Sky weather component."""
import re
import unittest
from unittest.mock import patch

import forecastio
import requests_mock

from homeassistant.components import weather
from homeassistant.util.unit_system import METRIC_SYSTEM
from homeassistant.setup import setup_component

from tests.common import load_fixture, get_test_home_assistant


class TestDarkSky(unittest.TestCase):
    """Test the Dark Sky weather component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        self.lat = self.hass.config.latitude = 37.8267
        self.lon = self.hass.config.longitude = -122.423

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    @patch('forecastio.api.get_forecast', wraps=forecastio.api.get_forecast)
    def test_setup(self, mock_req, mock_get_forecast):
        """Test for successfully setting up the forecast.io platform."""
        uri = (r'https://api.(darksky.net|forecast.io)\/forecast\/(\w+)\/'
               r'(-?\d+\.?\d*),(-?\d+\.?\d*)')
        mock_req.get(re.compile(uri),
                     text=load_fixture('darksky.json'))

        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'test',
                'platform': 'darksky',
                'api_key': 'foo',
            }
        })

        assert mock_get_forecast.called
        assert mock_get_forecast.call_count == 1

        state = self.hass.states.get('weather.test')
        assert state.state == 'sunny'
