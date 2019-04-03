"""The test for the World clock sensor platform."""
import unittest

from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant
import homeassistant.util.dt as dt_util


class TestWorldClockSensor(unittest.TestCase):
    """Test the World clock sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.time_zone = dt_util.get_time_zone('America/New_York')

        config = {
            'sensor': {
                'platform': 'worldclock',
                'time_zone': 'America/New_York',
            }
        }

        assert setup_component(self.hass, 'sensor', config)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_time(self):
        """Test the time at a different location."""
        state = self.hass.states.get('sensor.worldclock_sensor')
        assert state is not None

        assert state.state == dt_util.now(
            time_zone=self.time_zone).strftime('%H:%M')
