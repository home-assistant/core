"""The tests for SleepIQ binary sensor platform."""
import unittest
from unittest.mock import MagicMock

import requests_mock

from homeassistant.setup import setup_component
from homeassistant.components.binary_sensor import sleepiq

from tests.components.test_sleepiq import mock_responses
from tests.common import get_test_home_assistant


class TestSleepIQBinarySensorSetup(unittest.TestCase):
    """Tests the SleepIQ Binary Sensor platform."""

    DEVICES = []

    def add_entities(self, devices):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.username = 'foo'
        self.password = 'bar'
        self.config = {
            'username': self.username,
            'password': self.password,
        }

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock):
        """Test for successfully setting up the SleepIQ platform."""
        mock_responses(mock)

        setup_component(self.hass, 'sleepiq', {
            'sleepiq': self.config})

        sleepiq.setup_platform(self.hass,
                               self.config,
                               self.add_entities,
                               MagicMock())
        assert 2 == len(self.DEVICES)

        left_side = self.DEVICES[1]
        assert 'SleepNumber ILE Test1 Is In Bed' == left_side.name
        assert 'on' == left_side.state

        right_side = self.DEVICES[0]
        assert 'SleepNumber ILE Test2 Is In Bed' == right_side.name
        assert 'off' == right_side.state
