"""The tests for the Unifi WAP device tracker platform."""
import unittest
from unittest import mock
import urllib

from homeassistant.components.device_tracker import unifi as unifi
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from unifi import controller


class TestUnifiScanner(unittest.TestCase):
    """Test the Unifiy platform."""

    @mock.patch('homeassistant.components.device_tracker.unifi.UnifiScanner')
    @mock.patch.object(controller, 'Controller')
    def test_config_minimal(self, mock_ctrl, mock_scanner):
        """Test the setup with minimal configuration."""
        config = {
            'device_tracker': {
                CONF_USERNAME: 'foo',
                CONF_PASSWORD: 'password',
            }
        }
        result = unifi.get_scanner(None, config)
        self.assertEqual(unifi.UnifiScanner.return_value, result)
        mock_ctrl.assert_called_once_with('localhost', 'foo', 'password',
                                          8443, 'v4')
        mock_scanner.assert_called_once_with(mock_ctrl.return_value)

    @mock.patch('homeassistant.components.device_tracker.unifi.UnifiScanner')
    @mock.patch.object(controller, 'Controller')
    def test_config_full(self, mock_ctrl, mock_scanner):
        """Test the setup with full configuration."""
        config = {
            'device_tracker': {
                CONF_USERNAME: 'foo',
                CONF_PASSWORD: 'password',
                CONF_HOST: 'myhost',
                'port': 123,
            }
        }
        result = unifi.get_scanner(None, config)
        self.assertEqual(unifi.UnifiScanner.return_value, result)
        mock_ctrl.assert_called_once_with('myhost', 'foo', 'password',
                                          123, 'v4')
        mock_scanner.assert_called_once_with(mock_ctrl.return_value)

    @mock.patch('homeassistant.components.device_tracker.unifi.UnifiScanner')
    @mock.patch.object(controller, 'Controller')
    def test_config_error(self, mock_ctrl, mock_scanner):
        """Test for configuration errors."""
        config = {
            'device_tracker': {
                CONF_HOST: 'myhost',
                'port': 123,
            }
        }
        result = unifi.get_scanner(None, config)
        self.assertFalse(result)
        self.assertFalse(mock_ctrl.called)

    @mock.patch('homeassistant.components.device_tracker.unifi.UnifiScanner')
    @mock.patch.object(controller, 'Controller')
    def test_config_badport(self, mock_ctrl, mock_scanner):
        """Test the setup with a bad port."""
        config = {
            'device_tracker': {
                CONF_USERNAME: 'foo',
                CONF_PASSWORD: 'password',
                CONF_HOST: 'myhost',
                'port': 'foo',
            }
        }
        result = unifi.get_scanner(None, config)
        self.assertFalse(result)
        self.assertFalse(mock_ctrl.called)

    @mock.patch('homeassistant.components.device_tracker.unifi.UnifiScanner')
    @mock.patch.object(controller, 'Controller')
    def test_config_controller_failed(self, mock_ctrl, mock_scanner):
        """Test for controller failure."""
        config = {
            'device_tracker': {
                CONF_USERNAME: 'foo',
                CONF_PASSWORD: 'password',
            }
        }
        mock_ctrl.side_effect = urllib.error.HTTPError(
            '/', 500, 'foo', {}, None)
        result = unifi.get_scanner(None, config)
        self.assertFalse(result)

    def test_scanner_update(self):
        """Test the scanner update."""
        ctrl = mock.MagicMock()
        fake_clients = [
            {'mac': '123'},
            {'mac': '234'},
        ]
        ctrl.get_clients.return_value = fake_clients
        unifi.UnifiScanner(ctrl)
        ctrl.get_clients.assert_called_once_with()

    def test_scanner_update_error(self):
        """Test the scanner update for error."""
        ctrl = mock.MagicMock()
        ctrl.get_clients.side_effect = urllib.error.HTTPError(
            '/', 500, 'foo', {}, None)
        unifi.UnifiScanner(ctrl)

    def test_scan_devices(self):
        """Test the scanning for devices."""
        ctrl = mock.MagicMock()
        fake_clients = [
            {'mac': '123'},
            {'mac': '234'},
        ]
        ctrl.get_clients.return_value = fake_clients
        scanner = unifi.UnifiScanner(ctrl)
        self.assertEqual(set(['123', '234']), set(scanner.scan_devices()))

    def test_get_device_name(self):
        """Test the getting of device names."""
        ctrl = mock.MagicMock()
        fake_clients = [
            {'mac': '123', 'hostname': 'foobar'},
            {'mac': '234', 'name': 'Nice Name'},
            {'mac': '456'},
        ]
        ctrl.get_clients.return_value = fake_clients
        scanner = unifi.UnifiScanner(ctrl)
        self.assertEqual('foobar', scanner.get_device_name('123'))
        self.assertEqual('Nice Name', scanner.get_device_name('234'))
        self.assertEqual(None, scanner.get_device_name('456'))
        self.assertEqual(None, scanner.get_device_name('unknown'))
