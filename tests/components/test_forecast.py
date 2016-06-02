"""The tests for the forecast.io component."""
import json
import re
import os
import unittest
from unittest.mock import MagicMock, patch

import forecastio
import httpretty
import pytest
from requests.exceptions import HTTPError

from homeassistant.components.sensor import forecast
from homeassistant import core as ha


class TestForecastSetup(unittest.TestCase):
    """Test the forecast.io module."""
    def setUp(self):
        self.hass = ha.HomeAssistant()
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

        with pytest.raises(HTTPError):
            forecast.setup_platform(self.hass, self.config, MagicMock())

    @httpretty.activate
    @patch('forecastio.api.get_forecast', wraps=forecastio.api.get_forecast)
    def test_setup(self, mock_get_forecast):
        """Test for successfully setting up the forecast.io component."""
        def load_fixture_from_json():
            cwd = os.path.dirname(__file__)
            fixture_path = os.path.join(cwd, '..', 'fixtures', 'forecast.json')
            with open(fixture_path) as file:
                content = json.load(file)
            return json.dumps(content)

        # Mock out any calls to the actual API and
        # return the fixture json instead
        uri = 'api.forecast.io\/forecast\/(\w+)\/(-?\d+\.?\d*),(-?\d+\.?\d*)'
        httpretty.register_uri(
            httpretty.GET,
            re.compile(uri),
            body=load_fixture_from_json(),
        )
        # The following will raise an error if the regex for the mock was
        # incorrect and we actually try to go out to the internet.
        httpretty.HTTPretty.allow_net_connect = False

        forecast.setup_platform(self.hass, self.config, MagicMock())
        self.assertTrue(mock_get_forecast.called)
        self.assertEqual(mock_get_forecast.call_count, 2)
