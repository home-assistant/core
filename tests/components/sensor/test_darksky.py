"""The tests for the Dark Sky platform."""
import re
import unittest
from unittest.mock import MagicMock, patch

import forecastio
from requests.exceptions import HTTPError
import requests_mock
from datetime import timedelta

from homeassistant.components.sensor import darksky
from homeassistant.bootstrap import setup_component

from tests.common import load_fixture, get_test_home_assistant


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
        self.config = {
            'api_key': 'foo',
            'monitored_conditions': ['summary', 'icon'],
            'update_interval': timedelta(seconds=120),
        }
        self.lat = 37.8267
        self.lon = -122.423
        self.hass.config.latitude = self.lat
        self.hass.config.longitude = self.lon
        self.entities = []

    def test_setup_with_config(self):
        """Test the platform setup with configuration."""
        self.assertTrue(
            setup_component(self.hass, 'sensor', {'darksky': self.config}))

    def test_setup_no_latitude(self):
        """Test that the component is not loaded without required config."""
        self.hass.config.latitude = None
        self.assertFalse(darksky.setup_platform(self.hass, {}, MagicMock()))

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

        response = darksky.setup_platform(self.hass, self.config, MagicMock())
        self.assertFalse(response)

    @requests_mock.Mocker()
    @patch('forecastio.api.get_forecast', wraps=forecastio.api.get_forecast)
    def test_setup(self, mock_req, mock_get_forecast):
        """Test for successfully setting up the forecast.io platform."""
        uri = (r'https://api.(darksky.net|forecast.io)\/forecast\/(\w+)\/'
               r'(-?\d+\.?\d*),(-?\d+\.?\d*)')
        mock_req.get(re.compile(uri),
                     text=load_fixture('darksky.json'))
        darksky.setup_platform(self.hass, self.config, self.add_entities)
        self.assertTrue(mock_get_forecast.called)
        self.assertEqual(mock_get_forecast.call_count, 1)
        self.assertEqual(len(self.entities), 2)
