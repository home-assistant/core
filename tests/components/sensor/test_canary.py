"""The tests for the Canary sensor platform."""
import copy
import unittest
from unittest.mock import patch

from homeassistant.components import canary as base_canary
from homeassistant.components.canary import DATA_CANARY
from homeassistant.components.sensor import canary
from tests.common import (get_test_home_assistant)
from tests.components.test_canary import API_LOCATIONS

VALID_CONFIG = {
    "canary": {
        "username": "foo@bar.org",
        "password": "bar",
    }
}


class TestCanarySensorSetup(unittest.TestCase):
    """Test the Canary platform."""

    DEVICES = []

    def add_devices(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = copy.deepcopy(VALID_CONFIG)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.canary.CanaryData')
    def test_setup_sensors(self, mock_canary):
        """Test the Canary senskor class and methods."""

        base_canary.setup(self.hass, self.config)

        self.hass.data[DATA_CANARY] = mock_canary()
        self.hass.data[DATA_CANARY].locations = API_LOCATIONS

        canary.setup_platform(self.hass, self.config, self.add_devices, None)

        self.assertEqual(6, len(self.DEVICES))
