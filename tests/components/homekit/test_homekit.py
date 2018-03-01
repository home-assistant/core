"""Tests for the HomeKit component."""

import unittest
from unittest.mock import call, patch, ANY

import voluptuous as vol

# pylint: disable=unused-import
from pyhap.accessory_driver import AccessoryDriver  # noqa F401

from homeassistant import setup
from homeassistant.core import Event
from homeassistant.components.homekit import (
    CONF_PIN_CODE, HOMEKIT_FILE, HomeKit, valid_pin)
from homeassistant.const import (
    CONF_PORT, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

from tests.common import get_test_home_assistant
from tests.mock.homekit import get_patch_paths, PATH_HOMEKIT

PATH_ACC, _ = get_patch_paths()
IP_ADDRESS = '127.0.0.1'

CONFIG_MIN = {'homekit': {}}
CONFIG = {
    'homekit': {
        CONF_PORT: 11111,
        CONF_PIN_CODE: '987-65-432',
    }
}


class TestHomeKit(unittest.TestCase):
    """Test setup of HomeKit component and HomeKit class."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_validate_pincode(self):
        """Test async_setup with invalid config option."""
        schema = vol.Schema(valid_pin)

        for value in ('', '123-456-78', 'a23-45-678', '12345678', 1234):
            with self.assertRaises(vol.MultipleInvalid):
                schema(value)

        for value in ('123-45-678', '234-56-789'):
            self.assertTrue(schema(value))

    @patch(PATH_HOMEKIT + '.HomeKit')
    def test_setup_min(self, mock_homekit):
        """Test async_setup with minimal config option."""
        self.assertTrue(setup.setup_component(
            self.hass, 'homekit', CONFIG_MIN))

        self.assertEqual(mock_homekit.mock_calls,
                         [call(self.hass, 51826),
                          call().setup_bridge(b'123-45-678')])
        mock_homekit.reset_mock()

        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.block_till_done()

        self.assertEqual(mock_homekit.mock_calls,
                         [call().start_driver(ANY)])

    @patch(PATH_HOMEKIT + '.HomeKit')
    def test_setup_parameters(self, mock_homekit):
        """Test async_setup with full config option."""
        self.assertTrue(setup.setup_component(
            self.hass, 'homekit', CONFIG))

        self.assertEqual(mock_homekit.mock_calls,
                         [call(self.hass, 11111),
                          call().setup_bridge(b'987-65-432')])

    @patch('pyhap.accessory_driver.AccessoryDriver')
    def test_homekit_class(self, mock_acc_driver):
        """Test interaction between the HomeKit class and pyhap."""
        with patch(PATH_HOMEKIT + '.accessories.HomeBridge') as mock_bridge:
            homekit = HomeKit(self.hass, 51826)
            homekit.setup_bridge(b'123-45-678')

        mock_bridge.reset_mock()
        self.hass.states.set('demo.demo1', 'on')
        self.hass.states.set('demo.demo2', 'off')

        with patch(PATH_HOMEKIT + '.get_accessory') as mock_get_acc, \
            patch(PATH_HOMEKIT + '.import_types') as mock_import_types, \
                patch('homeassistant.util.get_local_ip') as mock_ip:
            mock_get_acc.side_effect = ['TempSensor', 'Window']
            mock_ip.return_value = IP_ADDRESS
            homekit.start_driver(Event(EVENT_HOMEASSISTANT_START))

        path = self.hass.config.path(HOMEKIT_FILE)

        self.assertEqual(mock_import_types.call_count, 1)
        self.assertEqual(mock_get_acc.call_count, 2)
        self.assertEqual(mock_bridge.mock_calls,
                         [call().add_accessory('TempSensor'),
                          call().add_accessory('Window')])
        self.assertEqual(mock_acc_driver.mock_calls,
                         [call(homekit.bridge, 51826, IP_ADDRESS, path),
                          call().start()])
        mock_acc_driver.reset_mock()

        self.hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
        self.hass.block_till_done()

        self.assertEqual(mock_acc_driver.mock_calls, [call().stop()])
