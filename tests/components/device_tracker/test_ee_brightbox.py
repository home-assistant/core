"""Tests for the EE BrightBox device scanner."""
from datetime import datetime
from asynctest import patch

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, ee_brightbox)
from homeassistant.const import (
    CONF_PLATFORM, CONF_USERNAME, CONF_PASSWORD, CONF_HOST)


def _get_devices_return_value():
    return [
        {
            'mac': 'AA:BB:CC:DD:EE:FF',
            'ip': '192.168.1.10',
            'hostname': 'hostnameAA',
            'activity_ip': True,
            'port': 'eth0',
            'time_last_active': datetime(2019, 1, 20, 16, 4, 0),
        },
        {
            'mac': '11:22:33:44:55:66',
            'hostname': 'hostname11',
            'ip': '192.168.1.11',
            'activity_ip': True,
            'port': 'wl0',
            'time_last_active': datetime(2019, 1, 20, 11, 9, 0),
        },
        {
            'mac': 'FF:FF:FF:FF:FF:FF',
            'hostname': 'hostnameFF',
            'ip': '192.168.1.12',
            'activity_ip': False,
            'port': 'wl1',
            'time_last_active': datetime(2019, 1, 15, 16, 9, 0),
        }
    ]


def _configure_scanner(eebrightbox_mock):
    config = {
        CONF_PASSWORD: 'password_test',
        'version': 2,
    }

    eebrightbox_instance = eebrightbox_mock.return_value
    eebrightbox_instance.__enter__.return_value = eebrightbox_instance
    eebrightbox_instance.get_devices.return_value = _get_devices_return_value()

    return ee_brightbox.EEBrightBoxScanner(config)


async def test_get_scanner_returns_instance(hass):
    """Test get scanner."""
    config = {
        ee_brightbox.DOMAIN: PLATFORM_SCHEMA({
            CONF_PLATFORM: ee_brightbox.DOMAIN,
            CONF_HOST: '192.168.1.1',
            CONF_USERNAME: 'username_test',
            CONF_PASSWORD: 'password_test',
            'version': 2,
        })
    }

    scanner = ee_brightbox.get_scanner(hass, config)
    assert isinstance(scanner, ee_brightbox.EEBrightBoxScanner)


@patch('eebrightbox.EEBrightBox')
async def test_scan_devices(eebrightbox_mock):
    """Test scanner scan devices."""
    scanner = _configure_scanner(eebrightbox_mock)
    devices = scanner.scan_devices()

    expected_devices = ['AA:BB:CC:DD:EE:FF', '11:22:33:44:55:66']

    assert sorted(devices) == sorted(expected_devices)


@patch('eebrightbox.EEBrightBox')
async def test_get_device_name_returns_device_hostname(eebrightbox_mock):
    """Test scanner get device name."""
    scanner = _configure_scanner(eebrightbox_mock)
    scanner.scan_devices()

    assert scanner.get_device_name('AA:BB:CC:DD:EE:FF') == 'hostnameAA'
    assert scanner.get_device_name('11:22:33:44:55:66') == 'hostname11'
    assert scanner.get_device_name('FF:FF:FF:FF:FF:FF') == 'hostnameFF'


@patch('eebrightbox.EEBrightBox')
async def test_get_extra_attributes(eebrightbox_mock):
    """Test scanner get extra attributes."""
    scanner = _configure_scanner(eebrightbox_mock)
    scanner.scan_devices()

    assert scanner.get_extra_attributes('AA:BB:CC:DD:EE:FF') == {
        'mac': 'AA:BB:CC:DD:EE:FF',
        'ip': '192.168.1.10',
        'port': 'eth0',
        'last_active': datetime(2019, 1, 20, 16, 4, 0)
    }
