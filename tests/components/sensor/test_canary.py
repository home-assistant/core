"""The tests for the Canary sensor platform."""
import copy
import unittest

import requests_mock

from homeassistant.components import canary as base_canary
from homeassistant.components.sensor import canary
from tests.common import (get_test_home_assistant)
from tests.components.test_canary import VALID_CONFIG, _setUpResponses


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

    @requests_mock.Mocker()
    def test_sensor(self, mock):
        """Test the Canary senskor class and methods."""
        _setUpResponses(mock)
        base_canary.setup(self.hass, self.config)
        canary.setup_platform(self.hass, self.config, self.add_devices, None)

        self.assertEqual(6, len(self.DEVICES))

        for device in self.DEVICES:
            device.update()

            if device.name == "New Home Family Room Air Quality":
                self.assertEqual(0.9, device.state)
            elif device.name == "New Home Family Room Humidity":
                self.assertEqual(32.1, device.state)
            elif device.name == "New Home Family Room Temperature":
                self.assertEqual(18.3, device.state)
            elif device.name == "Old Home Den Air Quality":
                self.assertEqual(0.7, device.state)
            elif device.name == "Old Home Den Humidity":
                self.assertEqual(50.2, device.state)
            elif device.name == "Old Home Den Temperature":
                self.assertEqual(15.3, device.state)
