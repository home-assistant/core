"""The tests for the Unifi direct device tracker platform."""
import os
from datetime import timedelta
from asynctest import mock, patch

import pytest
import voluptuous as vol

from homeassistant.setup import async_setup_component
from homeassistant.components import device_tracker
from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME, CONF_TRACK_NEW, CONF_AWAY_HIDE,
    CONF_NEW_DEVICE_DEFAULTS)
from homeassistant.components.unifi_direct.device_tracker import (
    DOMAIN, CONF_PORT, PLATFORM_SCHEMA, _response_to_json, get_scanner)
from homeassistant.const import (CONF_PLATFORM, CONF_PASSWORD, CONF_USERNAME,
                                 CONF_HOST)

from tests.common import (
    assert_setup_component, mock_component, load_fixture)

scanner_path = 'homeassistant.components.unifi_direct.device_tracker.' + \
    'UnifiDeviceScanner'


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, 'zone')
    yaml_devices = hass.config.path(device_tracker.YAML_DEVICES)
    yield
    if os.path.isfile(yaml_devices):
        os.remove(yaml_devices)


@patch(scanner_path, return_value=mock.MagicMock())
async def test_get_scanner(unifi_mock, hass):
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
        assert await async_setup_component(hass, DOMAIN, conf_dict)

    conf_dict[DOMAIN][CONF_PORT] = 22
    assert unifi_mock.call_args == mock.call(conf_dict[DOMAIN])


@patch('pexpect.pxssh.pxssh')
async def test_get_device_name(mock_ssh, hass):
    """Testing MAC matching."""
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
    scanner = get_scanner(hass, conf_dict)
    devices = scanner.scan_devices()
    assert 23 == len(devices)
    assert "iPhone" == \
        scanner.get_device_name("98:00:c6:56:34:12")
    assert "iPhone" == \
        scanner.get_device_name("98:00:C6:56:34:12")


@patch('pexpect.pxssh.pxssh.logout')
@patch('pexpect.pxssh.pxssh.login')
async def test_failed_to_log_in(mock_login, mock_logout, hass):
    """Testing exception at login results in False."""
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
    scanner = get_scanner(hass, conf_dict)
    assert not scanner


@patch('pexpect.pxssh.pxssh.logout')
@patch('pexpect.pxssh.pxssh.login', autospec=True)
@patch('pexpect.pxssh.pxssh.prompt')
@patch('pexpect.pxssh.pxssh.sendline')
async def test_to_get_update(mock_sendline, mock_prompt, mock_login,
                             mock_logout, hass):
    """Testing exception in get_update matching."""
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

    scanner = get_scanner(hass, conf_dict)
    # mock_sendline.side_effect = AssertionError("Test")
    mock_prompt.side_effect = AssertionError("Test")
    devices = scanner._get_update()  # pylint: disable=protected-access
    assert devices is None


def test_good_response_parses(hass):
    """Test that the response form the AP parses to JSON correctly."""
    response = _response_to_json(load_fixture('unifi_direct.txt'))
    assert response != {}


def test_bad_response_returns_none(hass):
    """Test that a bad response form the AP parses to JSON correctly."""
    assert _response_to_json("{(}") == {}


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
