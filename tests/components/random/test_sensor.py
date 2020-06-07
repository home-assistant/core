"""The test for the random number sensor platform."""
import unittest

from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestRandomSensor(unittest.TestCase):
    """Test the Random number sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_random_sensor(self):
        """Test the Random number sensor."""
        config = {
            "sensor": {
                "platform": "random",
                "name": "test",
                "minimum": 10,
                "maximum": 20,
            }
        }

        assert setup_component(self.hass, "sensor", config)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")

        assert int(state.state) <= config["sensor"]["maximum"]
        assert int(state.state) >= config["sensor"]["minimum"]
