"""The tests for the uptime sensor platform."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.components.sensor.uptime import UptimeSensor
from tests.common import get_test_home_assistant


class TestUptimeSensor(unittest.TestCase):
    """Test the uptime sensor."""

    def setUp(self):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_uptime_min_config(self):
        """Test minimum uptime configuration."""
        config = {
            'sensor': {
                'platform': 'uptime',
            }
        }
        assert setup_component(self.hass, 'sensor', config)

    def test_uptime_sensor_name_change(self):
        """Test uptime sensor with different name."""
        config = {
            'sensor': {
                'platform': 'uptime',
                'name': 'foobar',
            }
        }
        assert setup_component(self.hass, 'sensor', config)
