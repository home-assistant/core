"""Tests for Orange Funbox 3 device tracker platform."""
from datetime import datetime
from unittest import mock

import pytest
import requests_mock

from homeassistant.components.orange_funbox.device_tracker import (
    FunboxDeviceScanner,
)


NETWORK_DEVICE_MAC = 'SO:ME:MA:C'


@pytest.mark.usefixtures('mocked_api', 'utcnow')
def test_scan_devices(tracker):
    """Test scanning for active devices."""
    addresses = tracker.scan_devices()

    assert len(addresses) == 1
    assert addresses[0] == NETWORK_DEVICE_MAC


def test_get_device_name(tracker):
    """Test get device name by MAC address."""
    name = tracker.get_device_name(NETWORK_DEVICE_MAC)

    assert name == 'NetworkDevice'


def test_get_extra_attributes(tracker, utcnow):
    """Test get device extra attributes."""
    attributes = tracker.get_extra_attributes(NETWORK_DEVICE_MAC)
    assert attributes == dict(
        active=True,
        device_type='TestDevice',
        first_seen='2018-08-10T10:12:13Z',
        ip='192.168.1.10',
        last_connection='2019-01-10T10:12:13Z',
        last_update=utcnow,
        mac=NETWORK_DEVICE_MAC,
        name='NetworkDevice',
        signal_noise_ratio=15,
        signal_strength=-30,
    )


@pytest.fixture
def mocked_api(response):
    """Create mocked router API."""
    with requests_mock.Mocker() as m:
        m.post(
            'http://foo.bar/sysbus/Devices:get',
            json=response,
            status_code=200,
        )
        yield m


@pytest.fixture(scope='session')
def utcnow(request):
    """Freeze time at now()."""
    start_dt = datetime.utcnow()
    with mock.patch('homeassistant.util.dt.utcnow') as dt_utcnow:
        dt_utcnow.return_value = start_dt
        yield start_dt


@pytest.fixture
def response():
    """Test router response."""
    return {
        'status': [
            {
                'PhysAddress': NETWORK_DEVICE_MAC,
                'Name': 'NetworkDevice',
                'IPAddress': '192.168.1.10',
                'FirstSeen': '2018-08-10T10:12:13Z',
                'LastConnection': '2019-01-10T10:12:13Z',
                'DeviceType': 'TestDevice',
                'SignalStrength': -30,
                'SignalNoiseRatio': 15,
                'Active': True,
            },
            {
                'PhysAddress': 'SO:ME:MA:C2',
                'Name': 'NotActiveDevice',
                'Active': False,
            },
            {
                'PhysAddress': None,
                'Name': 'USBDevice',
                'Active': True,
            },
        ]
    }


@pytest.fixture(scope='session')
def tracker(config):
    """Build FunboxDeviceScanner."""
    return FunboxDeviceScanner(config)


@pytest.fixture(scope='session')
def config():
    """Test tracker config."""
    return {
        'host': 'foo.bar',
        'exclude': [],
    }
