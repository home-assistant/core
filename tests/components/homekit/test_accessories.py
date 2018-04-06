"""Test all functions related to the basic accessory implementation.

This includes tests for all mock object types.
"""
import unittest
from unittest.mock import call, patch, Mock

from homeassistant.components.homekit.accessories import (
    add_preload_service, set_accessory_info,
    HomeAccessory, HomeBridge, HomeDriver)
from homeassistant.components.homekit.const import (
    ACCESSORY_MODEL, ACCESSORY_NAME, BRIDGE_MODEL, BRIDGE_NAME,
    SERV_ACCESSORY_INFO, CHAR_MANUFACTURER, CHAR_MODEL,
    CHAR_NAME, CHAR_SERIAL_NUMBER)


class TestAccessories(unittest.TestCase):
    """Test pyhap adapter methods."""

    def test_add_preload_service(self):
        """Test add_preload_service without additional characteristics."""
        acc = Mock()
        serv = add_preload_service(acc, 'AirPurifier')
        self.assertEqual(acc.mock_calls, [call.add_service(serv)])
        with self.assertRaises(ValueError):
            serv.get_characteristic('Name')

        # Test with typo in service name
        with self.assertRaises(KeyError):
            add_preload_service(Mock(), 'AirPurifierTypo')

        # Test adding additional characteristic as string
        serv = add_preload_service(Mock(), 'AirPurifier', 'Name')
        serv.get_characteristic('Name')

        # Test adding additional characteristics as list
        serv = add_preload_service(Mock(), 'AirPurifier',
                                   ['Name', 'RotationSpeed'])
        serv.get_characteristic('Name')
        serv.get_characteristic('RotationSpeed')

        # Test adding additional characteristic with typo
        with self.assertRaises(KeyError):
            add_preload_service(Mock(), 'AirPurifier', 'NameTypo')

    def test_set_accessory_info(self):
        """Test setting the basic accessory information."""
        # Test HomeAccessory
        acc = HomeAccessory()
        set_accessory_info(acc, 'name', 'model', 'manufacturer', '0000')

        serv = acc.get_service(SERV_ACCESSORY_INFO)
        self.assertEqual(serv.get_characteristic(CHAR_NAME).value, 'name')
        self.assertEqual(serv.get_characteristic(CHAR_MODEL).value, 'model')
        self.assertEqual(
            serv.get_characteristic(CHAR_MANUFACTURER).value, 'manufacturer')
        self.assertEqual(
            serv.get_characteristic(CHAR_SERIAL_NUMBER).value, '0000')

        # Test HomeBridge
        acc = HomeBridge(None)
        set_accessory_info(acc, 'name', 'model', 'manufacturer', '0000')

        serv = acc.get_service(SERV_ACCESSORY_INFO)
        self.assertEqual(serv.get_characteristic(CHAR_MODEL).value, 'model')
        self.assertEqual(
            serv.get_characteristic(CHAR_MANUFACTURER).value, 'manufacturer')
        self.assertEqual(
            serv.get_characteristic(CHAR_SERIAL_NUMBER).value, '0000')

    def test_home_accessory(self):
        """Test HomeAccessory class."""
        acc = HomeAccessory()
        self.assertEqual(acc.display_name, ACCESSORY_NAME)
        self.assertEqual(acc.category, 1)  # Category.OTHER
        self.assertEqual(len(acc.services), 1)
        serv = acc.services[0]  # SERV_ACCESSORY_INFO
        self.assertEqual(
            serv.get_characteristic(CHAR_MODEL).value, ACCESSORY_MODEL)

        acc = HomeAccessory('test_name', 'test_model', 'FAN', aid=2)
        self.assertEqual(acc.display_name, 'test_name')
        self.assertEqual(acc.category, 3)  # Category.FAN
        self.assertEqual(acc.aid, 2)
        self.assertEqual(len(acc.services), 1)
        serv = acc.services[0]  # SERV_ACCESSORY_INFO
        self.assertEqual(
            serv.get_characteristic(CHAR_MODEL).value, 'test_model')

    def test_home_bridge(self):
        """Test HomeBridge class."""
        bridge = HomeBridge(None)
        self.assertEqual(bridge.display_name, BRIDGE_NAME)
        self.assertEqual(bridge.category, 2)  # Category.BRIDGE
        self.assertEqual(len(bridge.services), 1)
        serv = bridge.services[0]  # SERV_ACCESSORY_INFO
        self.assertEqual(serv.display_name, SERV_ACCESSORY_INFO)
        self.assertEqual(
            serv.get_characteristic(CHAR_MODEL).value, BRIDGE_MODEL)

        bridge = HomeBridge('hass', 'test_name', 'test_model')
        self.assertEqual(bridge.display_name, 'test_name')
        self.assertEqual(len(bridge.services), 1)
        serv = bridge.services[0]  # SERV_ACCESSORY_INFO
        self.assertEqual(
            serv.get_characteristic(CHAR_MODEL).value, 'test_model')

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
        self.assertEqual(mock_show_msg.call_args, call(bridge, 'hass'))

    def test_home_driver(self):
        """Test HomeDriver class."""
        bridge = HomeBridge(None)
        ip_address = '127.0.0.1'
        port = 51826
        path = '.homekit.state'

        with patch('pyhap.accessory_driver.AccessoryDriver.__init__') \
                as mock_driver:
            HomeDriver(bridge, ip_address, port, path)

        self.assertEqual(
            mock_driver.call_args, call(bridge, ip_address, port, path))
