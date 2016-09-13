"""The tests for SleepIQ binary_sensor platform."""
import unittest
from unittest.mock import MagicMock

import requests_mock

from homeassistant import core as ha
from homeassistant.components.binary_sensor import sleepiq

from tests.components.test_sleepiq import mock_responses


class TestSleepIQBinarySensorSetup(unittest.TestCase):
    """Tests the SleepIQ Binary Sensor platform."""

    DEVICES = []

    def add_devices(self, devices):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = ha.HomeAssistant()
        self.username = 'foo'
        self.password = 'bar'
        self.config = {
            'username': self.username,
            'password': self.password,
        }

    @requests_mock.Mocker()
    def test_setup(self, mock):
        """Test for succesfully setting up the SleepIQ platform."""
        mock_responses(mock)

        sleepiq.setup_platform(self.hass,
                               self.config,
                               self.add_devices,
                               MagicMock())
        self.assertEqual(2, len(self.DEVICES))

        left_side = self.DEVICES[1]
        self.assertEqual('SleepNumber ILE Test1 Is In Bed', left_side.name)
        self.assertEqual('on', left_side.state)

        right_side = self.DEVICES[0]
        self.assertEqual('SleepNumber ILE Test2 Is In Bed', right_side.name)
        self.assertEqual('off', right_side.state)
