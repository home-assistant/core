"""The tests for the Ring binary sensor platform."""
import unittest
from unittest import mock

from homeassistant.components.binary_sensor import ring
from homeassistant.components import ring as base_ring

from tests.components.test_ring import (
    mocked_requests_get, ATTRIBUTION, VALID_CONFIG)
from tests.common import get_test_home_assistant


class TestRingBinarySensorSetup(unittest.TestCase):
    """Test the Ring Binary Sensor platform."""

    DEVICES = []

    def add_devices(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = {
            'username': 'foo',
            'password': 'bar',
            'monitored_conditions': ['ding', 'motion'],
        }

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch('requests.Session.get', side_effect=mocked_requests_get)
    @mock.patch('requests.Session.post', side_effect=mocked_requests_get)
    def test_binary_sensor(self, get_mock, post_mock):
        """Test the Ring sensor class and methods."""
        base_ring.setup(self.hass, VALID_CONFIG)
        ring.setup_platform(self.hass,
                            self.config,
                            self.add_devices,
                            None)

        for device in self.DEVICES:
            device.update()
            if device.name == 'Front Door Ding':
                self.assertEqual('on', device.state)
                self.assertEqual('America/New_York',
                                 device.device_state_attributes['timezone'])
            elif device.name == 'Front Door Motion':
                self.assertEqual('off', device.state)
                self.assertEqual('motion', device.device_class)

            self.assertIsNone(device.entity_picture)
            self.assertEqual(ATTRIBUTION,
                             device.device_state_attributes['attribution'])
