"""The tests for the Unifi WAP device tracker platform."""
from unittest import mock
from pyunifi.controller import APIError
import homeassistant.util.dt as dt_util
from datetime import timedelta


import pytest
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN, unifi as unifi
from homeassistant.const import (CONF_HOST, CONF_USERNAME, CONF_PASSWORD,
                                 CONF_PLATFORM, CONF_VERIFY_SSL)
DEFAULT_DETECTION_TIME = timedelta(seconds=300)


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


@mock.patch('os.access', return_value=True)
@mock.patch('os.path.isfile', mock.Mock(return_value=True))
def test_config_valid_verify_ssl(hass, mock_scanner, mock_ctrl):
    """Test the setup with a string for ssl_verify.

    Representing the absolute path to a CA certificate bundle.
    """
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_VERIFY_SSL: "/tmp/unifi.crt"
        })
    }
    result = unifi.get_scanner(hass, config)
    assert mock_scanner.return_value == result
    assert mock_ctrl.call_count == 1
    assert mock_ctrl.mock_calls[0] == \
        mock.call('localhost', 'foo', 'password', 8443,
                  version='v4', site_id='default', ssl_verify="/tmp/unifi.crt")

    assert mock_scanner.call_count == 1
    assert mock_scanner.call_args == mock.call(mock_ctrl.return_value,
                                               DEFAULT_DETECTION_TIME,
                                               None)


def test_config_minimal(hass, mock_scanner, mock_ctrl):
    """Test the setup with minimal configuration."""
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
        })
    }
    result = unifi.get_scanner(hass, config)
    assert mock_scanner.return_value == result
    assert mock_ctrl.call_count == 1
    assert mock_ctrl.mock_calls[0] == \
        mock.call('localhost', 'foo', 'password', 8443,
                  version='v4', site_id='default', ssl_verify=True)

    assert mock_scanner.call_count == 1
    assert mock_scanner.call_args == mock.call(mock_ctrl.return_value,
                                               DEFAULT_DETECTION_TIME,
                                               None)


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
            'detection_time': 300,
        })
    }
    result = unifi.get_scanner(hass, config)
    assert mock_scanner.return_value == result
    assert mock_ctrl.call_count == 1
    assert mock_ctrl.call_args == \
        mock.call('myhost', 'foo', 'password', 123,
                  version='v4', site_id='abcdef01', ssl_verify=False)

    assert mock_scanner.call_count == 1
    assert mock_scanner.call_args == mock.call(mock_ctrl.return_value,
                                               DEFAULT_DETECTION_TIME,
                                               None)


def test_config_error():
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
    with pytest.raises(vol.Invalid):
        unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_VERIFY_SSL: "dfdsfsdfsd",  # Invalid ssl_verify (no file)
        })


def test_config_controller_failed(hass, mock_ctrl, mock_scanner):
    """Test for controller failure."""
    config = {
        'device_tracker': {
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
        }
    }
    mock_ctrl.side_effect = APIError(
        '/', 500, 'foo', {}, None)
    result = unifi.get_scanner(hass, config)
    assert result is False


def test_scanner_update():
    """Test the scanner update."""
    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123', 'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234', 'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
    ]
    ctrl.get_clients.return_value = fake_clients
    unifi.UnifiScanner(ctrl, DEFAULT_DETECTION_TIME, None)
    assert ctrl.get_clients.call_count == 1
    assert ctrl.get_clients.call_args == mock.call()


def test_scanner_update_error():
    """Test the scanner update for error."""
    ctrl = mock.MagicMock()
    ctrl.get_clients.side_effect = APIError(
        '/', 500, 'foo', {}, None)
    unifi.UnifiScanner(ctrl, DEFAULT_DETECTION_TIME, None)


def test_scan_devices():
    """Test the scanning for devices."""
    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123', 'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234', 'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
    ]
    ctrl.get_clients.return_value = fake_clients
    scanner = unifi.UnifiScanner(ctrl, DEFAULT_DETECTION_TIME, None)
    assert set(scanner.scan_devices()) == set(['123', '234'])


def test_scan_devices_filtered():
    """Test the scanning for devices based on SSID."""
    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123', 'essid': 'foonet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234', 'essid': 'foonet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '567', 'essid': 'notnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '890', 'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
    ]

    ssid_filter = ['foonet', 'barnet']
    ctrl.get_clients.return_value = fake_clients
    scanner = unifi.UnifiScanner(ctrl, DEFAULT_DETECTION_TIME, ssid_filter)
    assert set(scanner.scan_devices()) == set(['123', '234', '890'])


def test_get_device_name():
    """Test the getting of device names."""
    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123',
         'hostname': 'foobar',
         'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234',
         'name': 'Nice Name',
         'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '456',
         'essid': 'barnet',
         'last_seen': '1504786810'},
    ]
    ctrl.get_clients.return_value = fake_clients
    scanner = unifi.UnifiScanner(ctrl, DEFAULT_DETECTION_TIME, None)
    assert scanner.get_device_name('123') == 'foobar'
    assert scanner.get_device_name('234') == 'Nice Name'
    assert scanner.get_device_name('456') is None
    assert scanner.get_device_name('unknown') is None
