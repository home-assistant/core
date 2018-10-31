"""The tests for the ASUSWRT device tracker platform."""
import os
from datetime import timedelta
import unittest
from unittest import mock

from homeassistant.setup import setup_component
from homeassistant.components import device_tracker
from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME, CONF_TRACK_NEW, CONF_NEW_DEVICE_DEFAULTS,
    CONF_AWAY_HIDE)
from homeassistant.components.device_tracker.asuswrt import (
    CONF_PROTOCOL, CONF_MODE, DOMAIN, CONF_PORT)
from homeassistant.const import (CONF_PLATFORM, CONF_PASSWORD, CONF_USERNAME,
                                 CONF_HOST)

import pytest
from tests.common import (
    get_test_home_assistant, get_test_config_dir, assert_setup_component,
    mock_component)

FAKEFILE = None

VALID_CONFIG_ROUTER_SSH = {DOMAIN: {
    CONF_PLATFORM: 'asuswrt',
    CONF_HOST: 'fake_host',
    CONF_USERNAME: 'fake_user',
    CONF_PROTOCOL: 'ssh',
    CONF_MODE: 'router',
    CONF_PORT: '22'
}}


def setup_module():
    """Set up the test module."""
    global FAKEFILE
    FAKEFILE = get_test_config_dir('fake_file')
    with open(FAKEFILE, 'w') as out:
        out.write(' ')


def teardown_module():
    """Tear down the module."""
    os.remove(FAKEFILE)


@pytest.mark.skip(
    reason="These tests are performing actual failing network calls. They "
    "need to be cleaned up before they are re-enabled. They're frequently "
    "failing in Travis.")
class TestComponentsDeviceTrackerASUSWRT(unittest.TestCase):
    """Tests for the ASUSWRT device tracker platform."""

    hass = None

    def setup_method(self, _):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, 'zone')

    def teardown_method(self, _):
        """Stop everything that was started."""
        self.hass.stop()
        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    def test_password_or_pub_key_required(self):
        """Test creating an AsusWRT scanner without a pass or pubkey."""
        with assert_setup_component(0, DOMAIN):
            assert setup_component(
                self.hass, DOMAIN, {DOMAIN: {
                    CONF_PLATFORM: 'asuswrt',
                    CONF_HOST: 'fake_host',
                    CONF_USERNAME: 'fake_user',
                    CONF_PROTOCOL: 'ssh'
                }})

    @mock.patch(
        'homeassistant.components.device_tracker.asuswrt.AsusWrtDeviceScanner',
        return_value=mock.MagicMock())
    def test_get_scanner_with_password_no_pubkey(self, asuswrt_mock):
        """Test creating an AsusWRT scanner with a password and no pubkey."""
        conf_dict = {
            DOMAIN: {
                CONF_PLATFORM: 'asuswrt',
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

        conf_dict[DOMAIN][CONF_MODE] = 'router'
        conf_dict[DOMAIN][CONF_PROTOCOL] = 'ssh'
        conf_dict[DOMAIN][CONF_PORT] = 22
        assert asuswrt_mock.call_count == 1
        assert asuswrt_mock.call_args == mock.call(conf_dict[DOMAIN])
