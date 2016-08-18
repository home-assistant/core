"""The tests for the ASUSWRT device tracker platform."""

import os
import unittest
from unittest import mock

from homeassistant.components import device_tracker
from homeassistant.const import (CONF_PLATFORM, CONF_PASSWORD, CONF_USERNAME,
                                 CONF_HOST)

from tests.common import get_test_home_assistant


class TestComponentsDeviceTrackerASUSWRT(unittest.TestCase):
    """Tests for the ASUSWRT device tracker platform."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    def test_password_or_pub_key_required(self):
        """Test creating an AsusWRT scanner without a pass or pubkey."""
        self.assertIsNone(device_tracker.asuswrt.get_scanner(
            self.hass, {device_tracker.DOMAIN: {
                CONF_PLATFORM: 'asuswrt',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user'
            }}))

    @mock.patch(
        'homeassistant.components.device_tracker.asuswrt.AsusWrtDeviceScanner',
        return_value=mock.MagicMock())
    def test_get_scanner_with_password_no_pubkey(self, asuswrt_mock):
        """Test creating an AsusWRT scanner with a password and no pubkey."""
        conf_dict = {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: 'asuswrt',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
                CONF_PASSWORD: 'fake_pass'
            }
        }
        self.assertIsNotNone(device_tracker.asuswrt.get_scanner(
            self.hass, conf_dict))
        asuswrt_mock.assert_called_once_with(conf_dict[device_tracker.DOMAIN])

    @mock.patch(
        'homeassistant.components.device_tracker.asuswrt.AsusWrtDeviceScanner',
        return_value=mock.MagicMock())
    def test_get_scanner_with_pubkey_no_password(self, asuswrt_mock):
        """Test creating an AsusWRT scanner with a pubkey and no password."""
        conf_dict = {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: 'asuswrt',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
                'pub_key': '/fake_path'
            }
        }
        self.assertIsNotNone(device_tracker.asuswrt.get_scanner(
            self.hass, conf_dict))
        asuswrt_mock.assert_called_once_with(conf_dict[device_tracker.DOMAIN])

    def test_ssh_login_with_pub_key(self):
        """Test that login is done with pub_key when configured to."""
        ssh = mock.MagicMock()
        ssh_mock = mock.patch('pexpect.pxssh.pxssh', return_value=ssh)
        ssh_mock.start()
        self.addCleanup(ssh_mock.stop)
        conf_dict = {
                CONF_PLATFORM: 'asuswrt',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
                'pub_key': '/fake_path'
        }
        update_mock = mock.patch(
            'homeassistant.components.device_tracker.asuswrt.'
            'AsusWrtDeviceScanner.get_asuswrt_data')
        update_mock.start()
        self.addCleanup(update_mock.stop)
        asuswrt = device_tracker.asuswrt.AsusWrtDeviceScanner(conf_dict)
        asuswrt.ssh_connection()
        ssh.login.assert_called_once_with('fake_host', 'fake_user',
                                          ssh_key='/fake_path')

    def test_ssh_login_with_password(self):
        """Test that login is done with password when configured to."""
        ssh = mock.MagicMock()
        ssh_mock = mock.patch('pexpect.pxssh.pxssh', return_value=ssh)
        ssh_mock.start()
        self.addCleanup(ssh_mock.stop)
        conf_dict = {
                CONF_PLATFORM: 'asuswrt',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
                CONF_PASSWORD: 'fake_pass'
        }
        update_mock = mock.patch(
            'homeassistant.components.device_tracker.asuswrt.'
            'AsusWrtDeviceScanner.get_asuswrt_data')
        update_mock.start()
        self.addCleanup(update_mock.stop)
        asuswrt = device_tracker.asuswrt.AsusWrtDeviceScanner(conf_dict)
        asuswrt.ssh_connection()
        ssh.login.assert_called_once_with('fake_host', 'fake_user',
                                          'fake_pass')

    def test_ssh_login_without_password_or_pubkey(self):
        """Test that login is not called without password or pub_key."""
        ssh = mock.MagicMock()
        ssh_mock = mock.patch('pexpect.pxssh.pxssh', return_value=ssh)
        ssh_mock.start()
        self.addCleanup(ssh_mock.stop)
        conf_dict = {
                CONF_PLATFORM: 'asuswrt',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
        }
        update_mock = mock.patch(
            'homeassistant.components.device_tracker.asuswrt.'
            'AsusWrtDeviceScanner.get_asuswrt_data')
        update_mock.start()
        self.addCleanup(update_mock.stop)
        asuswrt = device_tracker.asuswrt.AsusWrtDeviceScanner(conf_dict)
        result = asuswrt.ssh_connection()
        ssh.login.assert_not_called()
        self.assertIsNone(result)
