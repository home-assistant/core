"""The tests for the tube_state platform."""
import unittest

import requests_mock

from homeassistant.components.london_air.sensor import CONF_LOCATIONS, URL
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, load_fixture

VALID_CONFIG = {"platform": "london_air", CONF_LOCATIONS: ["Merton"]}


class TestLondonAirSensor(unittest.TestCase):
    """Test the tube_state platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock_req):
        """Test for operational tube_state sensor with proper attributes."""
        mock_req.get(URL, text=load_fixture("london_air.json"))
        assert setup_component(self.hass, "sensor", {"sensor": self.config})
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.merton")
        assert state.state == "Low"
        assert state.attributes.get("updated") == "2017-08-03 03:00:00"
        assert state.attributes.get("sites") == 2
        assert state.attributes.get("data")[0]["site_code"] == "ME2"
