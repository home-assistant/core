"""The tests for the SleepIQ component."""
import unittest

from homeassistant import core as ha
import homeassistant.components.sleepiq as sleepiq


class TestSleepIQ(unittest.TestCase):
    """Tests the SleepIQ component."""

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
        """Test the setup."""
        sleepiq.setup(self.hass, self.config)
