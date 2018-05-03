"""Test all functions related to the basic accessory implementation.

This includes tests for all mock object types.
"""
from datetime import datetime, timedelta
import unittest
from unittest.mock import call, patch, Mock

from homeassistant.components.homekit.accessories import (
    debounce, HomeAccessory, HomeBridge, HomeDriver)
from homeassistant.components.homekit.const import (
    BRIDGE_MODEL, BRIDGE_NAME, BRIDGE_SERIAL_NUMBER, SERV_ACCESSORY_INFO,
    CHAR_FIRMWARE_REVISION, CHAR_MANUFACTURER, CHAR_MODEL, CHAR_NAME,
    CHAR_SERIAL_NUMBER, MANUFACTURER)
from homeassistant.const import __version__, ATTR_NOW, EVENT_TIME_CHANGED
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant


def patch_debounce():
    """Return patch for debounce method."""
    return patch('homeassistant.components.homekit.accessories.debounce',
                 lambda f: lambda *args, **kwargs: f(*args, **kwargs))


class TestAccessories(unittest.TestCase):
    """Test pyhap adapter methods."""

    def test_debounce(self):
        """Test add_timeout decorator function."""
        def demo_func(*args):
            nonlocal arguments, counter
            counter += 1
            arguments = args

        arguments = None
        counter = 0
        hass = get_test_home_assistant()
        mock = Mock(hass=hass)

        debounce_demo = debounce(demo_func)
        self.assertEqual(debounce_demo.__name__, 'demo_func')
        now = datetime(2018, 1, 1, 20, 0, 0, tzinfo=dt_util.UTC)

        with patch('homeassistant.util.dt.utcnow', return_value=now):
            debounce_demo(mock, 'value')
        hass.bus.fire(
            EVENT_TIME_CHANGED, {ATTR_NOW: now + timedelta(seconds=3)})
        hass.block_till_done()
        assert counter == 1
        assert len(arguments) == 2

        with patch('homeassistant.util.dt.utcnow', return_value=now):
            debounce_demo(mock, 'value')
            debounce_demo(mock, 'value')

        hass.bus.fire(
            EVENT_TIME_CHANGED, {ATTR_NOW: now + timedelta(seconds=3)})
        hass.block_till_done()
        assert counter == 2

        hass.stop()

    def test_home_accessory(self):
        """Test HomeAccessory class."""
        hass = get_test_home_assistant()

        acc = HomeAccessory(hass, 'Home Accessory', 'homekit.accessory', 2)
        self.assertEqual(acc.hass, hass)
        self.assertEqual(acc.display_name, 'Home Accessory')
        self.assertEqual(acc.category, 1)  # Category.OTHER
        self.assertEqual(len(acc.services), 1)
        serv = acc.services[0]  # SERV_ACCESSORY_INFO
        self.assertEqual(serv.display_name, SERV_ACCESSORY_INFO)
        self.assertEqual(
            serv.get_characteristic(CHAR_NAME).value, 'Home Accessory')
        self.assertEqual(
            serv.get_characteristic(CHAR_MANUFACTURER).value, MANUFACTURER)
        self.assertEqual(
            serv.get_characteristic(CHAR_MODEL).value, 'Homekit')
        self.assertEqual(serv.get_characteristic(CHAR_SERIAL_NUMBER).value,
                         'homekit.accessory')

        hass.states.set('homekit.accessory', 'on')
        hass.block_till_done()
        acc.run()
        hass.states.set('homekit.accessory', 'off')
        hass.block_till_done()

        acc = HomeAccessory('hass', 'test_name', 'test_model.demo', 2)
        self.assertEqual(acc.display_name, 'test_name')
        self.assertEqual(acc.aid, 2)
        self.assertEqual(len(acc.services), 1)
        serv = acc.services[0]  # SERV_ACCESSORY_INFO
        self.assertEqual(
            serv.get_characteristic(CHAR_MODEL).value, 'Test Model')

        hass.stop()

    def test_home_bridge(self):
        """Test HomeBridge class."""
        bridge = HomeBridge('hass')
        self.assertEqual(bridge.hass, 'hass')
        self.assertEqual(bridge.display_name, BRIDGE_NAME)
        self.assertEqual(bridge.category, 2)  # Category.BRIDGE
        self.assertEqual(len(bridge.services), 1)
        serv = bridge.services[0]  # SERV_ACCESSORY_INFO
        self.assertEqual(serv.display_name, SERV_ACCESSORY_INFO)
        self.assertEqual(
            serv.get_characteristic(CHAR_NAME).value, BRIDGE_NAME)
        self.assertEqual(
            serv.get_characteristic(CHAR_FIRMWARE_REVISION).value, __version__)
        self.assertEqual(
            serv.get_characteristic(CHAR_MANUFACTURER).value, MANUFACTURER)
        self.assertEqual(
            serv.get_characteristic(CHAR_MODEL).value, BRIDGE_MODEL)
        self.assertEqual(
            serv.get_characteristic(CHAR_SERIAL_NUMBER).value,
            BRIDGE_SERIAL_NUMBER)

        bridge = HomeBridge('hass', 'test_name')
        self.assertEqual(bridge.display_name, 'test_name')
        self.assertEqual(len(bridge.services), 1)
        serv = bridge.services[0]  # SERV_ACCESSORY_INFO

        # setup_message
        bridge.setup_message()

        # add_paired_client
        with patch('pyhap.accessory.Accessory.add_paired_client') \
            as mock_add_paired_client, \
            patch('homeassistant.components.homekit.accessories.'
                  'dismiss_setup_message') as mock_dissmiss_msg:
            bridge.add_paired_client('client_uuid', 'client_public')

        self.assertEqual(mock_add_paired_client.call_args,
                         call('client_uuid', 'client_public'))
        self.assertEqual(mock_dissmiss_msg.call_args, call('hass'))

        # remove_paired_client
        with patch('pyhap.accessory.Accessory.remove_paired_client') \
            as mock_remove_paired_client, \
            patch('homeassistant.components.homekit.accessories.'
                  'show_setup_message') as mock_show_msg:
            bridge.remove_paired_client('client_uuid')

        self.assertEqual(
            mock_remove_paired_client.call_args, call('client_uuid'))
        self.assertEqual(mock_show_msg.call_args, call('hass', bridge))

    def test_home_driver(self):
        """Test HomeDriver class."""
        bridge = HomeBridge('hass')
        ip_address = '127.0.0.1'
        port = 51826
        path = '.homekit.state'

        with patch('pyhap.accessory_driver.AccessoryDriver.__init__') \
                as mock_driver:
            HomeDriver(bridge, ip_address, port, path)

        self.assertEqual(
            mock_driver.call_args, call(bridge, ip_address, port, path))
