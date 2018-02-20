"""Tests for the homekit component."""

import unittest
from unittest.mock import patch

import voluptuous as vol

from homeassistant import setup
from homeassistant.core import Event
from homeassistant.components.homekit import (
    CONF_PIN_CODE, BRIDGE_NAME, Homekit, valid_pin)
from homeassistant.components.homekit.covers import Window
from homeassistant.components.homekit.sensors import TemperatureSensor
from homeassistant.const import (
    CONF_PORT, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

from tests.common import get_test_home_assistant

HOMEKIT_PATH = 'homeassistant.components.homekit'

CONFIG_MIN = {'homekit': {}}
CONFIG = {
    'homekit': {
        CONF_PORT: 11111,
        CONF_PIN_CODE: '987-65-432',
    }
}


class TestHomekit(unittest.TestCase):
    """Test the Multicover component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everthing that was started."""
        self.hass.stop()

    @patch(HOMEKIT_PATH + '.Homekit.start_driver')
    @patch(HOMEKIT_PATH + '.Homekit.setup_bridge')
    @patch(HOMEKIT_PATH + '.Homekit.__init__')
    def test_setup_min(self, mock_homekit, mock_setup_bridge,
                       mock_start_driver):
        """Test async_setup with minimal config option."""
        mock_homekit.return_value = None

        self.assertTrue(setup.setup_component(
            self.hass, 'homekit', CONFIG_MIN))

        mock_homekit.assert_called_once_with(self.hass, 51826)
        mock_setup_bridge.assert_called_with(b'123-45-678')
        mock_start_driver.assert_not_called()

        self.hass.start()
        self.hass.block_till_done()
        self.assertEqual(mock_start_driver.call_count, 1)

    @patch(HOMEKIT_PATH + '.Homekit.start_driver')
    @patch(HOMEKIT_PATH + '.Homekit.setup_bridge')
    @patch(HOMEKIT_PATH + '.Homekit.__init__')
    def test_setup_parameters(self, mock_homekit, mock_setup_bridge,
                              mock_start_driver):
        """Test async_setup with full config option."""
        mock_homekit.return_value = None

        self.assertTrue(setup.setup_component(
            self.hass, 'homekit', CONFIG))

        mock_homekit.assert_called_once_with(self.hass, 11111)
        mock_setup_bridge.assert_called_with(b'987-65-432')

    def test_validate_pincode(self):
        """Test async_setup with invalid config option."""
        schema = vol.Schema(valid_pin)

        for value in ('', '123-456-78', 'a23-45-678', '12345678'):
            with self.assertRaises(vol.MultipleInvalid):
                schema(value)

        for value in ('123-45-678', '234-56-789'):
            self.assertTrue(schema(value))

    @patch('pyhap.accessory_driver.AccessoryDriver.persist')
    @patch('pyhap.accessory_driver.AccessoryDriver.stop')
    @patch('pyhap.accessory_driver.AccessoryDriver.start')
    @patch(HOMEKIT_PATH + '.import_types')
    @patch(HOMEKIT_PATH + '.get_accessory')
    def test_homekit_pyhap_interaction(
            self, mock_get_accessory, mock_import_types,
            mock_driver_start, mock_driver_stop, mock_file_persist):
        """Test the interaction between the homekit class and pyhap."""
        acc1 = TemperatureSensor(self.hass, 'sensor.temp', 'Temperature')
        acc2 = Window(self.hass, 'cover.hall_window', 'Cover')
        mock_get_accessory.side_effect = [acc1, acc2]

        homekit = Homekit(self.hass, 51826)
        homekit.setup_bridge(b'123-45-678')

        self.assertEqual(homekit.bridge.display_name, BRIDGE_NAME)

        self.hass.states.set('demo.demo1', 'on')
        self.hass.states.set('demo.demo2', 'off')

        self.hass.start()
        self.hass.block_till_done()

        homekit.start_driver(Event(EVENT_HOMEASSISTANT_START))

        self.assertEqual(mock_get_accessory.call_count, 2)
        self.assertEqual(mock_import_types.call_count, 1)
        self.assertEqual(mock_driver_start.call_count, 1)

        accessories = homekit.bridge.accessories
        self.assertEqual(accessories[2], acc1)
        self.assertEqual(accessories[3], acc2)

        mock_driver_stop.assert_not_called()

        self.hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
        self.hass.block_till_done()

        self.assertEqual(mock_driver_stop.call_count, 1)
