"""The tests for the Vultr sensor platform."""
import pytest
import unittest
import requests_mock
import voluptuous as vol

from components.sensor import vultr
from components import vultr as base_vultr
from components.vultr import CONF_SUBSCRIPTION
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, CONF_PLATFORM, CONF_NAME)

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
            CONF_SUBSCRIPTION: '576965',
            CONF_NAME: 'my-amazing-server',
            CONF_MONITORED_CONDITIONS: [
                'current_bandwidth_gb',
                'pending_charges'
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

        self.assertEqual(2, len(self.DEVICES))

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

    def test_invalid_sensor_config(self):
        """Test config type failures."""
        with pytest.raises(vol.Invalid):  # No subscription
            vultr.PLATFORM_SCHEMA({
                CONF_PLATFORM: base_vultr.DOMAIN,
                CONF_MONITORED_CONDITIONS: vultr.MONITORED_CONDITIONS
            })
        with pytest.raises(vol.Invalid):  # No monitored_conditions
            vultr.PLATFORM_SCHEMA({
                CONF_PLATFORM: base_vultr.DOMAIN,
            })
        with pytest.raises(vol.Invalid):  # Bad monitored_conditions
            vultr.PLATFORM_SCHEMA({
                CONF_PLATFORM: base_vultr.DOMAIN,
                CONF_SUBSCRIPTION: '123456',
                CONF_MONITORED_CONDITIONS: [
                    'non-existent-condition',
                ]
            })

    @requests_mock.Mocker()
    def test_invalid_sensors(self, mock):
        """Test the VultrSensor fails."""
        mock.get(
            'https://api.vultr.com/v1/account/info?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_account_info.json'))

        mock.get(
            'https://api.vultr.com/v1/server/list?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_server_list.json'))

        base_vultr.setup(self.hass, VALID_CONFIG)

        bad_conf = {
            CONF_MONITORED_CONDITIONS: vultr.MONITORED_CONDITIONS,
        }  # No subs at all

        no_sub_setup = vultr.setup_platform(self.hass,
                                            bad_conf,
                                            self.add_devices,
                                            None)

        self.assertFalse(no_sub_setup)
        self.assertEqual(0, len(self.DEVICES))

        bad_conf = {
            CONF_SUBSCRIPTION: '123456',
            CONF_MONITORED_CONDITIONS: ['bad-condition',
                                        'non-existing-condition'],
        }  # Invalid monitored_conditions

        bad_conditions_setup = vultr.setup_platform(self.hass,
                                                    bad_conf,
                                                    self.add_devices,
                                                    None)

        self.assertFalse(bad_conditions_setup)
        self.assertEqual(0, len(self.DEVICES))
