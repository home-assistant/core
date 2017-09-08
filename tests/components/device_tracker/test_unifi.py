"""The tests for the Unifi WAP device tracker platform."""
from unittest import mock
from pyunifi.controller import APIError

import pytest
import voluptuous as vol

from homeassistant.components.device_tracker import (DOMAIN,
                                                     unifi as unifi)
from homeassistant.const import (CONF_HOST, CONF_USERNAME, CONF_PASSWORD,
                                 CONF_PLATFORM, CONF_VERIFY_SSL)
import homeassistant.util.dt as dt_util


@pytest.fixture
def mock_ctrl():
    """Mock pyunifi."""
    with mock.patch('pyunifi.controller.Controller') as mock_control:
        yield mock_control


@pytest.fixture
def mock_scanner():
    """Mock UnifyScanner."""
    with mock.patch('homeassistant.components.device_tracker'
                    '.unifi.UnifiScanner') as scanner:
        yield scanner


def test_config_minimal(hass, mock_scanner, mock_ctrl):
    """Test the setup with minimal configuration."""
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
        })
    }
    """ Check that scanner works """
    result = unifi.get_scanner(hass, config)
    assert mock_scanner.return_value == result
    assert result is not None
    assert mock_scanner.call_count == 1
    args, kwargs = mock_scanner.call_args_list[0]
    arg = args[0]
    assert arg == config['device_tracker']


def test_config_full(hass, mock_scanner, mock_ctrl):
    """Test the setup with full configuration."""
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_HOST: 'myhost',
            CONF_VERIFY_SSL: False,
            'port': 123,
            'site_id': 'abcdef01',
            'api': 'v4'
        })
    }
    result = unifi.get_scanner(hass, config)
    assert mock_scanner.return_value == result
    assert result is not None
    assert mock_scanner.call_count == 1
    args, kwargs = mock_scanner.call_args_list[0]
    arg = args[0]
    assert arg == config['device_tracker']


def test_config_error(hass):
    """Test for configuration errors."""
    with pytest.raises(vol.Invalid):
        unifi.PLATFORM_SCHEMA({
            # no username
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_HOST: 'myhost',
            'port': 123,
        })
    with pytest.raises(vol.Invalid):
        unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_HOST: 'myhost',
            'port': 'foo',  # bad port!
        })
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            'api': 'v6'
        })
    }
    result = unifi.get_scanner(hass, config)
    assert result is None


def test_config_controller_failed(hass, mock_ctrl):
    """Test for controller failure."""
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_HOST: 'myhost',
            CONF_VERIFY_SSL: False,
            'port': 123,
            'site_id': 'abcdef01',
            'api': 'v4'
        })
    }
    mock_ctrl.side_effect = APIError(
        '/', 500, 'foo', {}, None)
    result = unifi.get_scanner(hass, config, ectrl=mock_ctrl)
    assert result is None


def test_scanner_update(hass):
    """Test the scanner update."""
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_HOST: 'myhost',
            CONF_VERIFY_SSL: False,
            'port': 123,
            'site_id': 'abcdef01',
            'api': 'v4'
        })
    }
    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123', 'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234', 'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
    ]
    ctrl().get_clients.return_value = fake_clients
    result = unifi.get_scanner(hass, config, ectrl=ctrl)
    assert ctrl().get_clients.call_count == 1
    assert ctrl().get_clients.call_args == mock.call()
    assert len(result.scan_devices()) == 2


def test_scanner_update_error(hass):
    """Test the scanner update for error."""
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_HOST: 'myhost',
            CONF_VERIFY_SSL: False,
            'port': 123,
            'site_id': 'abcdef01',
            'api': 'v4'
        })
    }

    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123', 'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234', 'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
    ]
    ctrl().get_clients.return_value = fake_clients
    ctrl().get_clients.side_effect = APIError(
        '/', 500, 'foo', {}, None)
    result = unifi.get_scanner(hass, config, ectrl=ctrl)
    assert len(result.scan_devices()) == 0


def test_scan_devices(hass):
    """Test the scanning for devices."""
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_HOST: 'myhost',
            CONF_VERIFY_SSL: False,
            'port': 123,
            'site_id': 'abcdef01',
            'api': 'v4'
        })
    }

    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123', 'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234', 'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
    ]
    ctrl().get_clients.return_value = fake_clients
    result = unifi.get_scanner(hass, config, ectrl=ctrl)
    devices = result.scan_devices()
    assert len(devices) == 2
    assert set(devices) == set(['123', '234'])


def test_get_device_name(hass):
    """Test the getting of device names."""
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_HOST: 'myhost',
            CONF_VERIFY_SSL: False,
            'port': 123,
            'site_id': 'abcdef01',
            'api': 'v4'
        })
    }

    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123',
         'hostname': 'foobar',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234',
         'name': 'Nice Name',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '456',
         'last_seen': '1504786810'},
    ]
    ctrl().get_clients.return_value = fake_clients
    scanner = unifi.get_scanner(hass, config, ectrl=ctrl)
    assert scanner.get_device_name('123') == 'foobar'
    assert scanner.get_device_name('234') == 'Nice Name'
    assert scanner.get_device_name('456') is None
    assert scanner.get_device_name('unknown') is None
