"""The tests for SleepIQ sensor platform."""
import unittest
from unittest.mock import MagicMock

from homeassistant import core as ha
from homeassistant.components.sensor import sleepiq


class TestSleepIQSensorSetup(unittest.TestCase):
    """Tests the SleepIQ Sensor platform."""

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
