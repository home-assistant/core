"""Test the Vultr binary sensor platform."""
import unittest
import requests_mock

from components.binary_sensor import vultr
from components import vultr as base_vultr
from components.vultr import (
    ATTR_ALLOWED_BANDWIDTH_GB, ATTR_AUTO_BACKUPS, ATTR_IPV4_ADDRESS,
    ATTR_COST_PER_MONTH, ATTR_CREATED_AT, ATTR_SUBSCRIPTION_ID)

from tests.components.test_vultr import VALID_CONFIG
from tests.common import (
    get_test_home_assistant, load_fixture)


class TestVultrBinarySensorSetup(unittest.TestCase):
    """Test the Vultr binary sensor platform."""

    DEVICES = []

    def add_devices(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Init values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = {
            "subs": [
                "576965",
                "123456"
            ]
        }

    def tearDown(self):
        """Stop our started services."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_binary_sensor(self, mock):
        """Test successful instance."""
        mock.get(
            'https://api.vultr.com/v1/account/info?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_account_info.json'))

        mock.get(
            'https://api.vultr.com/v1/server/list?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_server_list.json'))

        base_vultr.setup(self.hass, VALID_CONFIG)
        vultr.setup_platform(self.hass,
                             self.config,
                             self.add_devices,
                             None)

        self.assertEqual(len(self.DEVICES), 2)

        for device in self.DEVICES:
            device.update()
            device_attrs = device.device_state_attributes

            if device.name == 'my new server':
                self.assertEqual('on', device.state)
                self.assertEqual('mdi:server', device.icon)
                self.assertEqual('1000',
                                 device_attrs[ATTR_ALLOWED_BANDWIDTH_GB])
                self.assertEqual('yes',
                                 device_attrs[ATTR_AUTO_BACKUPS])
                self.assertEqual('123.123.123.123',
                                 device_attrs[ATTR_IPV4_ADDRESS])
                self.assertEqual('10.05',
                                 device_attrs[ATTR_COST_PER_MONTH])
                self.assertEqual('2013-12-19 14:45:41',
                                 device_attrs[ATTR_CREATED_AT])
                self.assertEqual('576965',
                                 device_attrs[ATTR_SUBSCRIPTION_ID])
            elif device.name == 'my failed server':
                self.assertEqual('off', device.state)
                self.assertEqual('mdi:server-off', device.icon)
                self.assertEqual('100',
                                 device_attrs[ATTR_ALLOWED_BANDWIDTH_GB])
                self.assertEqual('no',
                                 device_attrs[ATTR_AUTO_BACKUPS])
                self.assertEqual('192.168.100.50',
                                 device_attrs[ATTR_IPV4_ADDRESS])
                self.assertEqual('73.25',
                                 device_attrs[ATTR_COST_PER_MONTH])
                self.assertEqual('2014-10-13 14:45:41',
                                 device_attrs[ATTR_CREATED_AT])
                self.assertEqual('123456',
                                 device_attrs[ATTR_SUBSCRIPTION_ID])

    @requests_mock.Mocker()
    def test_invalid_binary_sensor(self, mock):
        """Test failed instance."""

        self.assertFalse(base_vultr.setup(self.hass, {"vultr": {}}))
        setup = vultr.setup_platform(self.hass,
                                     self.config,
                                     self.add_devices,
                                     None)

        self.assertFalse(setup)
