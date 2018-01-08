"""Test the Vultr binary sensor platform."""
import json
import unittest
from unittest.mock import patch

import requests_mock
import pytest
import voluptuous as vol

from homeassistant.components.binary_sensor import vultr
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
    def test_binary_sensor(self, mock):
        """Test successful instance."""
        mock.get(
            'https://api.vultr.com/v1/account/info?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_account_info.json'))

        with patch(
            'vultr.Vultr.server_list',
            return_value=json.loads(
                load_fixture('vultr_server_list.json'))):
            # Setup hub
            base_vultr.setup(self.hass, VALID_CONFIG)

        # Setup each of our test configs
        for config in self.configs:
            vultr.setup_platform(self.hass,
                                 config,
                                 self.add_devices,
                                 None)

        self.assertEqual(len(self.DEVICES), 3)

        for device in self.DEVICES:

            # Test pre data retieval
            if device.subscription == '555555':
                self.assertEqual('Vultr {}', device.name)

            device.update()
            device_attrs = device.device_state_attributes

            if device.subscription == '555555':
                self.assertEqual('Vultr Another Server', device.name)

            if device.name == 'A Server':
                self.assertEqual(True, device.is_on)
                self.assertEqual('power', device.device_class)
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

    def test_invalid_sensor_config(self):
        """Test config type failures."""
        with pytest.raises(vol.Invalid):  # No subs
            vultr.PLATFORM_SCHEMA({
                CONF_PLATFORM: base_vultr.DOMAIN,
            })

    @requests_mock.Mocker()
    def test_invalid_sensors(self, mock):
        """Test the VultrBinarySensor fails."""
        mock.get(
            'https://api.vultr.com/v1/account/info?api_key=ABCDEFG1234567',
            text=load_fixture('vultr_account_info.json'))

        with patch(
            'vultr.Vultr.server_list',
            return_value=json.loads(
                load_fixture('vultr_server_list.json'))):
            # Setup hub
            base_vultr.setup(self.hass, VALID_CONFIG)

        bad_conf = {}  # No subscription

        no_subs_setup = vultr.setup_platform(self.hass,
                                             bad_conf,
                                             self.add_devices,
                                             None)

        self.assertFalse(no_subs_setup)

        bad_conf = {
            CONF_NAME: "Missing Server",
            CONF_SUBSCRIPTION: '555555'
        }  # Sub not associated with API key (not in server_list)

        wrong_subs_setup = vultr.setup_platform(self.hass,
                                                bad_conf,
                                                self.add_devices,
                                                None)

        self.assertFalse(wrong_subs_setup)
