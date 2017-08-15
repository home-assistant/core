"""The tests for the Ring binary sensor platform."""
import os
import unittest
import requests_mock

from homeassistant.components.binary_sensor import ring
from homeassistant.components import ring as base_ring

from tests.components.test_ring import ATTRIBUTION, VALID_CONFIG
from tests.common import (
    get_test_config_dir, get_test_home_assistant, load_fixture)


class TestRingBinarySensorSetup(unittest.TestCase):
    """Test the Ring Binary Sensor platform."""

    DEVICES = []

    def add_devices(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def cleanup(self):
        """Cleanup any data created from the tests."""
        if os.path.isfile(self.cache):
            os.remove(self.cache)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.cache = get_test_config_dir(base_ring.DEFAULT_CACHEDB)
        self.config = {
            'username': 'foo',
            'password': 'bar',
            'monitored_conditions': ['ding', 'motion'],
        }

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()
        self.cleanup()

    @requests_mock.Mocker()
    def test_binary_sensor(self, mock):
        """Test the Ring sensor class and methods."""
        mock.post('https://api.ring.com/clients_api/session',
                  text=load_fixture('ring_session.json'))
        mock.get('https://api.ring.com/clients_api/ring_devices',
                 text=load_fixture('ring_devices.json'))
        mock.get('https://api.ring.com/clients_api/dings/active',
                 text=load_fixture('ring_ding_active.json'))

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
