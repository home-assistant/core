"""The tests for the Dark Sky platform."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.components import sensor

from tests.common import get_test_home_assistant

CONDITIONS = ["stationname", "temperature"]
BASE_CONFIG = {
    "sensor": [
        {
            "platform": "buienradar",
            "name": "volkel",
            "latitude": 51.65,
            "longitude": 5.7,
            "monitored_conditions": CONDITIONS,
        }
    ]
}


class TestBuienradarSensorSetup(unittest.TestCase):
    """Test the Buienradar sensor platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test for successfully set-up with default config.

        Smoke test.
        """
        assert setup_component(self.hass, sensor.DOMAIN, BASE_CONFIG)

        for cond in CONDITIONS:
            state = self.hass.states.get(f"sensor.volkel_{cond}")
            assert state.state == "unknown"
