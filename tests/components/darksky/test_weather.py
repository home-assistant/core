"""The tests for the Dark Sky weather component."""
import re
import unittest

import forecastio
from requests.exceptions import ConnectionError
import requests_mock

from homeassistant.components import weather
from homeassistant.setup import setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.async_mock import patch
from tests.common import get_test_home_assistant, load_fixture


class TestDarkSky(unittest.TestCase):
    """Test the Dark Sky weather component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        self.lat = self.hass.config.latitude = 37.8267
        self.lon = self.hass.config.longitude = -122.423
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    @patch("forecastio.api.get_forecast", wraps=forecastio.api.get_forecast)
    def test_setup(self, mock_req, mock_get_forecast):
        """Test for successfully setting up the forecast.io platform."""
        uri = (
            r"https://api.(darksky.net|forecast.io)\/forecast\/(\w+)\/"
            r"(-?\d+\.?\d*),(-?\d+\.?\d*)"
        )
        mock_req.get(re.compile(uri), text=load_fixture("darksky.json"))

        assert setup_component(
            self.hass,
            weather.DOMAIN,
            {"weather": {"name": "test", "platform": "darksky", "api_key": "foo"}},
        )
        self.hass.block_till_done()

        assert mock_get_forecast.called
        assert mock_get_forecast.call_count == 1

        state = self.hass.states.get("weather.test")
        assert state.state == "sunny"

    @patch("forecastio.load_forecast", side_effect=ConnectionError())
    def test_failed_setup(self, mock_load_forecast):
        """Test to ensure that a network error does not break component state."""

        assert setup_component(
            self.hass,
            weather.DOMAIN,
            {"weather": {"name": "test", "platform": "darksky", "api_key": "foo"}},
        )
        self.hass.block_till_done()

        state = self.hass.states.get("weather.test")
        assert state.state == "unavailable"
