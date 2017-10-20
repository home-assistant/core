"""The tests for the Vultr sensor platform."""
import unittest
import requests_mock

from components.sensor import vultr
from components import vultr as base_vultr

from tests.components.test_vultr import VALID_CONFIG
from tests.common import (
    get_test_home_assistant, load_fixture)


class TestVultrSensorSetup(unittest.TestCase):
    """Test the Vultr platform."""

    DEVICES = []

    def add_devices(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = {
            "subs": [
                "576965",
                "123456"
            ],
            "monitored_conditions": [
                "current_bandwidth_gb",
                "pending_charges"
            ]
        }

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_sensor(self, mock):
        """Test the Vultr sensor class and methods."""
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

        self.assertEqual(4, len(self.DEVICES))

        for device in self.DEVICES:
            device.update()

            if device.name == 'my new server Current Bandwidth Used':
                self.assertEqual(131.51, device.state)
                self.assertEqual('GB', device.unit_of_measurement)
                self.assertEqual('mdi:chart-histogram', device.icon)
            elif device.name == 'my new server Pending Charges':
                self.assertEqual(46.67, device.state)
                self.assertEqual('US$', device.unit_of_measurement)
                self.assertEqual('mdi:currency-usd', device.icon)
            elif device.name == 'my failed server Current Bandwidth Used':
                self.assertEqual(957.46, device.state)
            elif device.name == 'my failed server Pending Charges':
                self.assertEqual("not a number", device.state)

    @requests_mock.Mocker()
    def test_invalid_sensor(self, mock):
        """Test the Vultr sensor class and methods."""
        mock.get('https://api.vultr.com/v1/account/info',
            text="{}")

        mock.get('https://api.vultr.com/v1/server/list')

        self.assertFalse(
            base_vultr.setup(self.hass, {"vultr": {}}))

        setup = vultr.setup_platform(self.hass,
                                     self.config,
                                     self.add_devices,
                                     None)

        self.assertFalse(setup)

        with pytest.raises(vol.Invalid):
            vultr.PLATFORM_SCHEMA({
                # No subs
            })
