"""The tests for the Unifi WAP device tracker platform."""
from collections import deque
from copy import copy
from unittest.mock import Mock
from datetime import timedelta

import pytest

from aiounifi.clients import Clients
from aiounifi.devices import Devices

from homeassistant import config_entries
from homeassistant.components import unifi
from homeassistant.components.unifi.const import (
    CONF_CONTROLLER, CONF_SITE_ID, UNIFI_CONFIG)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL)
from homeassistant.setup import async_setup_component

import homeassistant.components.device_tracker as device_tracker
import homeassistant.components.unifi.device_tracker as unifi_dt
import homeassistant.util.dt as dt_util

DEFAULT_DETECTION_TIME = timedelta(seconds=300)

CLIENT_1 = {
    'essid': 'ssid',
    'hostname': 'client_1',
    'ip': '10.0.0.1',
    'is_wired': False,
    'last_seen': 1562600145,
    'mac': '00:00:00:00:00:01',
}
CLIENT_2 = {
    'hostname': 'client_2',
    'ip': '10.0.0.2',
    'is_wired': True,
    'last_seen': 1562600145,
    'mac': '00:00:00:00:00:02',
    'name': 'Wired Client',
}
CLIENT_3 = {
    'essid': 'ssid2',
    'hostname': 'client_3',
    'ip': '10.0.0.3',
    'is_wired': False,
    'last_seen': 1562600145,
    'mac': '00:00:00:00:00:03',
}

CONTROLLER_DATA = {
    CONF_HOST: 'mock-host',
    CONF_USERNAME: 'mock-user',
    CONF_PASSWORD: 'mock-pswd',
    CONF_PORT: 1234,
    CONF_SITE_ID: 'mock-site',
    CONF_VERIFY_SSL: True
}

ENTRY_CONFIG = {
    CONF_CONTROLLER: CONTROLLER_DATA
}

CONTROLLER_ID = unifi.CONTROLLER_ID.format(host='mock-host', site='mock-site')


@pytest.fixture
def mock_controller(hass):
    """Mock a UniFi Controller."""
    hass.data[UNIFI_CONFIG] = {}
    controller = unifi.UniFiController(hass, None)

    controller.api = Mock()
    controller.mock_requests = []

    controller.mock_client_responses = deque()
    controller.mock_device_responses = deque()

    async def mock_request(method, path, **kwargs):
        kwargs['method'] = method
        kwargs['path'] = path
        controller.mock_requests.append(kwargs)
        if path == 's/{site}/stat/sta':
            return controller.mock_client_responses.popleft()
        if path == 's/{site}/stat/device':
            return controller.mock_device_responses.popleft()
        return None

    controller.api.clients = Clients({}, mock_request)
    controller.api.devices = Devices({}, mock_request)

    return controller


async def setup_controller(hass, mock_controller):
    """Load the UniFi switch platform with the provided controller."""
    hass.config.components.add(unifi.DOMAIN)
    hass.data[unifi.DOMAIN] = {CONTROLLER_ID: mock_controller}
    config_entry = config_entries.ConfigEntry(
        1, unifi.DOMAIN, 'Mock Title', ENTRY_CONFIG, 'test',
        config_entries.CONN_CLASS_LOCAL_POLL)
    mock_controller.config_entry = config_entry

    await mock_controller.async_update()
    await hass.config_entries.async_forward_entry_setup(
        config_entry, device_tracker.DOMAIN)

    await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a bridge."""
    assert await async_setup_component(hass, device_tracker.DOMAIN, {
        device_tracker.DOMAIN: {
            'platform': 'unifi'
        }
    }) is True
    assert unifi.DOMAIN not in hass.data


async def test_no_clients(hass, mock_controller):
    """Test the update_clients function when no clients are found."""
    mock_controller.mock_client_responses.append({})
    mock_controller.mock_device_responses.append({})

    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 2
    assert len(hass.states.async_all()) == 2


async def test_tracked_devices(hass, mock_controller):
    """Test the update_items function with some clients."""
    mock_controller.mock_client_responses.append(
        [CLIENT_1, CLIENT_2, CLIENT_3])
    mock_controller.mock_device_responses.append({})
    mock_controller.unifi_config = {unifi_dt.CONF_SSID_FILTER: ['ssid']}

    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 2
    assert len(hass.states.async_all()) == 4

    device_1 = hass.states.get('device_tracker.client_1')
    assert device_1 is not None
    assert device_1.state == 'not_home'

    device_2 = hass.states.get('device_tracker.wired_client')
    assert device_2 is not None
    assert device_2.state == 'not_home'

    device_3 = hass.states.get('device_tracker.client_3')
    assert device_3 is None

    client_1 = copy(CLIENT_1)
    client_1['last_seen'] = dt_util.as_timestamp(dt_util.utcnow())
    mock_controller.mock_client_responses.append([client_1])
    mock_controller.mock_device_responses.append({})
    await mock_controller.async_update()
    await hass.async_block_till_done()

    device_1 = hass.states.get('device_tracker.client_1')
    assert device_1.state == 'home'
