"""Test the Vultr switch platform."""
import unittest
import requests_mock
import pytest
import voluptuous as vol

from homeassistant.components.switch import vultr
from homeassistant.components import vultr as base_vultr
from homeassistant.components.vultr import (
    ATTR_ALLOWED_BANDWIDTH, ATTR_AUTO_BACKUPS, ATTR_IPV4_ADDRESS,
    ATTR_COST_PER_MONTH, ATTR_CREATED_AT, ATTR_SUBSCRIPTION_ID,
    CONF_SUBSCRIPTION)
from homeassistant.const import (
    CONF_PLATFORM, CONF_NAME)

from tests.components.test_vultr import VALID_CONFIG
from tests.common import (
    get_test_home_assistant, load_fixture)


class TestVultrSwitchSetup(unittest.TestCase):
    """Test the Vultr switch platform."""

    DEVICES = []

    def add_devices(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Init values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.configs = [
            {
                CONF_SUBSCRIPTION: '576965',
                CONF_NAME: "A Server"
            },
            {
                CONF_SUBSCRIPTION: '123456',
                CONF_NAME: "Failed Server"
            },
            {
                CONF_SUBSCRIPTION: '555555',
                CONF_NAME: vultr.DEFAULT_NAME
            }
        ]

    def tearDown(self):
        """Stop our started services."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_switch(self, mock):
        """Test successful instance."""
        mock.get(
            'https://api.vultr.com/v1/account/info?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_account_info.json'))

        mock.get(
            'https://api.vultr.com/v1/server/list?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_server_list.json'))

        # Setup hub
        base_vultr.setup(self.hass, VALID_CONFIG)

        # Setup each of our test configs
        for config in self.configs:
            vultr.setup_platform(self.hass,
                                 config,
                                 self.add_devices,
                                 None)

        self.assertEqual(len(self.DEVICES), 3)

        tested = 0

        for device in self.DEVICES:
            if device.subscription == '555555':
                self.assertEqual('Vultr {}', device.name)
                tested += 1

            device.update()
            device_attrs = device.device_state_attributes

            if device.subscription == '555555':
                self.assertEqual('Vultr Another Server', device.name)
                tested += 1

            if device.name == 'A Server':
                self.assertEqual(True, device.is_on)
                self.assertEqual('on', device.state)
                self.assertEqual('mdi:server', device.icon)
                self.assertEqual('1000',
                                 device_attrs[ATTR_ALLOWED_BANDWIDTH])
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
                tested += 1

            elif device.name == 'Failed Server':
                self.assertEqual(False, device.is_on)
                self.assertEqual('off', device.state)
                self.assertEqual('mdi:server-off', device.icon)
                self.assertEqual('1000',
                                 device_attrs[ATTR_ALLOWED_BANDWIDTH])
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
                tested += 1

        self.assertEqual(4, tested)

    @requests_mock.Mocker()
    def test_turn_on(self, mock):
        """Test turning a subscription on."""
        mock.get(
            'https://api.vultr.com/v1/server/list?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_server_list.json'))

        mock.post(
            'https://api.vultr.com/v1/server/start?api_key=ABCDEFG1234567')

        for device in self.DEVICES:
            if device.name == 'Failed Server':
                device.turn_on()

        # Turn on, force date update
        self.assertEqual(2, mock.call_count)

    @requests_mock.Mocker()
    def test_turn_off(self, mock):
        """Test turning a subscription off."""
        mock.get(
            'https://api.vultr.com/v1/server/list?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_server_list.json'))

        mock.post(
            'https://api.vultr.com/v1/server/halt?api_key=ABCDEFG1234567')

        for device in self.DEVICES:
            if device.name == 'A Server':
                device.turn_off()

        # Turn off, force update
        self.assertEqual(2, mock.call_count)

    def test_invalid_switch_config(self):
        """Test config type failures."""
        with pytest.raises(vol.Invalid):  # No subscription
            vultr.PLATFORM_SCHEMA({
                CONF_PLATFORM: base_vultr.DOMAIN,
            })

    @requests_mock.Mocker()
    def test_invalid_switches(self, mock):
        """Test the VultrSwitch fails."""
        mock.get(
            'https://api.vultr.com/v1/account/info?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_account_info.json'))

        mock.get(
            'https://api.vultr.com/v1/server/list?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_server_list.json'))

        base_vultr.setup(self.hass, VALID_CONFIG)

        bad_conf = {}  # No subscription

        no_subs_setup = vultr.setup_platform(self.hass,
                                             bad_conf,
                                             self.add_devices,
                                             None)

        self.assertIsNotNone(no_subs_setup)

        bad_conf = {
            CONF_NAME: "Missing Server",
            CONF_SUBSCRIPTION: '665544'
        }  # Sub not associated with API key (not in server_list)

        wrong_subs_setup = vultr.setup_platform(self.hass,
                                                bad_conf,
                                                self.add_devices,
                                                None)

        self.assertIsNotNone(wrong_subs_setup)
