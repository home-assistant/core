"""The tests for the buienradar weather component."""
import unittest

from homeassistant.components import weather
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


# Example config snippet from documentation.
BASE_CONFIG = {
    "weather": [
        {
            "platform": "buienradar",
            "name": "volkel",
            "latitude": 51.65,
            "longitude": 5.7,
            "forecast": True,
        }
    ]
}


class TestBuienradarWeather(unittest.TestCase):
    """Test the Buienradar weather component."""

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
        assert setup_component(self.hass, weather.DOMAIN, BASE_CONFIG)

        state = self.hass.states.get("weather.volkel")
        assert state.state == "unknown"
