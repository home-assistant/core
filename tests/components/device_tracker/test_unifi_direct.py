"""The tests for the Unifi direct device tracker platform."""
import os
from datetime import timedelta
import unittest
from unittest import mock
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.setup import setup_component
from homeassistant.components import device_tracker
from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME, CONF_TRACK_NEW, CONF_AWAY_HIDE,
    CONF_NEW_DEVICE_DEFAULTS)
from homeassistant.components.device_tracker.unifi_direct import (
    DOMAIN, CONF_PORT, PLATFORM_SCHEMA, _response_to_json, get_scanner)
from homeassistant.const import (CONF_PLATFORM, CONF_PASSWORD, CONF_USERNAME,
                                 CONF_HOST)

from tests.common import (
    get_test_home_assistant, assert_setup_component,
    mock_component, load_fixture)


class TestComponentsDeviceTrackerUnifiDirect(unittest.TestCase):
    """Tests for the Unifi direct device tracker platform."""

    hass = None
    scanner_path = 'homeassistant.components.device_tracker.' + \
        'unifi_direct.UnifiDeviceScanner'

    def setup_method(self, _):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, 'zone')

    def teardown_method(self, _):
        """Stop everything that was started."""
        self.hass.stop()
        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    @mock.patch(scanner_path,
                return_value=mock.MagicMock())
    def test_get_scanner(self, unifi_mock):  \
            # pylint: disable=invalid-name
        """Test creating an Unifi direct scanner with a password."""
        conf_dict = {
            DOMAIN: {
                CONF_PLATFORM: 'unifi_direct',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
                CONF_PASSWORD: 'fake_pass',
                CONF_TRACK_NEW: True,
                CONF_CONSIDER_HOME: timedelta(seconds=180),
                CONF_NEW_DEVICE_DEFAULTS: {
                    CONF_TRACK_NEW: True,
                    CONF_AWAY_HIDE: False
                }
            }
        }

        with assert_setup_component(1, DOMAIN):
            assert setup_component(self.hass, DOMAIN, conf_dict)

        conf_dict[DOMAIN][CONF_PORT] = 22
        self.assertEqual(unifi_mock.call_args, mock.call(conf_dict[DOMAIN]))

    @patch('pexpect.pxssh.pxssh')
    def test_get_device_name(self, mock_ssh):
        """"Testing MAC matching."""
        conf_dict = {
            DOMAIN: {
                CONF_PLATFORM: 'unifi_direct',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
                CONF_PASSWORD: 'fake_pass',
                CONF_PORT: 22,
                CONF_TRACK_NEW: True,
                CONF_CONSIDER_HOME: timedelta(seconds=180)
            }
        }
        mock_ssh.return_value.before = load_fixture('unifi_direct.txt')
        scanner = get_scanner(self.hass, conf_dict)
        devices = scanner.scan_devices()
        self.assertEqual(23, len(devices))
        self.assertEqual("iPhone",
                         scanner.get_device_name("98:00:c6:56:34:12"))
        self.assertEqual("iPhone",
                         scanner.get_device_name("98:00:C6:56:34:12"))

    @patch('pexpect.pxssh.pxssh.logout')
    @patch('pexpect.pxssh.pxssh.login')
    def test_failed_to_log_in(self, mock_login, mock_logout):
        """"Testing exception at login results in False."""
        from pexpect import exceptions

        conf_dict = {
            DOMAIN: {
                CONF_PLATFORM: 'unifi_direct',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
                CONF_PASSWORD: 'fake_pass',
                CONF_PORT: 22,
                CONF_TRACK_NEW: True,
                CONF_CONSIDER_HOME: timedelta(seconds=180)
            }
        }

        mock_login.side_effect = exceptions.EOF("Test")
        scanner = get_scanner(self.hass, conf_dict)
        self.assertFalse(scanner)

    @patch('pexpect.pxssh.pxssh.logout')
    @patch('pexpect.pxssh.pxssh.login', autospec=True)
    @patch('pexpect.pxssh.pxssh.prompt')
    @patch('pexpect.pxssh.pxssh.sendline')
    def test_to_get_update(self, mock_sendline, mock_prompt, mock_login,
                           mock_logout):
        """"Testing exception in get_update matching."""
        conf_dict = {
            DOMAIN: {
                CONF_PLATFORM: 'unifi_direct',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
                CONF_PASSWORD: 'fake_pass',
                CONF_PORT: 22,
                CONF_TRACK_NEW: True,
                CONF_CONSIDER_HOME: timedelta(seconds=180)
            }
        }

        scanner = get_scanner(self.hass, conf_dict)
        # mock_sendline.side_effect = AssertionError("Test")
        mock_prompt.side_effect = AssertionError("Test")
        devices = scanner._get_update()  # pylint: disable=protected-access
        self.assertTrue(devices is None)

    def test_good_reponse_parses(self):
        """Test that the response form the AP parses to JSON correctly."""
        response = _response_to_json(load_fixture('unifi_direct.txt'))
        self.assertTrue(response != {})

    def test_bad_reponse_returns_none(self):
        """Test that a bad response form the AP parses to JSON correctly."""
        self.assertTrue(_response_to_json("{(}") == {})


def test_config_error():
    """Test for configuration errors."""
    with pytest.raises(vol.Invalid):
        PLATFORM_SCHEMA({
            # no username
            CONF_PASSWORD: 'password',
            CONF_PLATFORM: DOMAIN,
            CONF_HOST: 'myhost',
            'port': 123,
        })
    with pytest.raises(vol.Invalid):
        PLATFORM_SCHEMA({
            # no password
            CONF_USERNAME: 'foo',
            CONF_PLATFORM: DOMAIN,
            CONF_HOST: 'myhost',
            'port': 123,
        })
    with pytest.raises(vol.Invalid):
        PLATFORM_SCHEMA({
            CONF_PLATFORM: DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_HOST: 'myhost',
            'port': 'foo',  # bad port!
        })
