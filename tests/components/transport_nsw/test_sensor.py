"""The tests for the Transport NSW (AU) sensor platform."""
import unittest

from homeassistant.setup import setup_component

from tests.async_mock import patch
from tests.common import get_test_home_assistant

VALID_CONFIG = {
    "sensor": {
        "platform": "transport_nsw",
        "stop_id": "209516",
        "route": "199",
        "destination": "",
        "api_key": "YOUR_API_KEY",
    }
}


def get_departuresMock(_stop_id, route, destination, api_key):
    """Mock TransportNSW departures loading."""
    data = {
        "stop_id": "209516",
        "route": "199",
        "due": 16,
        "delay": 6,
        "real_time": "y",
        "destination": "Palm Beach",
        "mode": "Bus",
    }
    return data


class TestRMVtransportSensor(unittest.TestCase):
    """Test the TransportNSW sensor."""

    def setUp(self):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch("TransportNSW.TransportNSW.get_departures", side_effect=get_departuresMock)
    def test_transportnsw_config(self, mock_get_departures):
        """Test minimal TransportNSW configuration."""
        assert setup_component(self.hass, "sensor", VALID_CONFIG)
        state = self.hass.states.get("sensor.next_bus")
        assert state.state == "16"
        assert state.attributes["stop_id"] == "209516"
        assert state.attributes["route"] == "199"
        assert state.attributes["delay"] == 6
        assert state.attributes["real_time"] == "y"
        assert state.attributes["destination"] == "Palm Beach"
        assert state.attributes["mode"] == "Bus"
