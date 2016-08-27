"""The tests for SleepIQ binary_sensor platform."""
import unittest
from unittest.mock import MagicMock

from homeassistant import core as ha
from homeassistant.components.binary_sensor import sleepiq


class TestSleepIQBinarySensorSetup(unittest.TestCase):
    """Tests the SleepIQ Binary Sensor platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = ha.HomeAssistant()
        self.username = 'foo'
        self.password = 'bar'
        self.config = {
            'username': self.username,
            'password': self.password,
        }

    def test_setup(self):
        """Test for succesfully setting up the SleepIQ platform."""
        sleepiq.setup_platform(self.hass, self.config, MagicMock())
