"""UniFi POE control platform tests."""
from collections import deque
from unittest.mock import Mock

import pytest

import aiounifi
from aiounifi.clients import Clients
from aiounifi.devices import Devices

from homeassistant import config_entries
from homeassistant.components import unifi
from homeassistant.setup import async_setup_component

import homeassistant.components.switch as switch

from tests.common import mock_coro

CLIENT_1 = {
    'hostname': 'client_1',
    'ip': '10.0.0.1',
    'is_wired': True,
    'mac': '00:00:00:00:00:01',
    'name': 'POE Client 1',
    'oui': 'Producer',
    'sw_mac': '00:00:00:00:01:01',
    'sw_port': 1,
    'wired-rx_bytes': 1234000000,
    'wired-tx_bytes': 5678000000
}
CLIENT_2 = {
    'hostname': 'client_2',
    'ip': '10.0.0.2',
    'is_wired': True,
    'mac': '00:00:00:00:00:02',
    'name': 'POE Client 2',
    'oui': 'Producer',
    'sw_mac': '00:00:00:00:01:01',
    'sw_port': 2,
    'wired-rx_bytes': 1234000000,
    'wired-tx_bytes': 5678000000
}
CLIENT_3 = {
    'hostname': 'client_3',
    'ip': '10.0.0.3',
    'is_wired': True,
    'mac': '00:00:00:00:00:03',
    'name': 'Non-POE Client 3',
    'oui': 'Producer',
    'sw_mac': '00:00:00:00:01:01',
    'sw_port': 3,
    'wired-rx_bytes': 1234000000,
    'wired-tx_bytes': 5678000000
}
CLIENT_4 = {
    'hostname': 'client_4',
    'ip': '10.0.0.4',
    'is_wired': True,
    'mac': '00:00:00:00:00:04',
    'name': 'Non-POE Client 4',
    'oui': 'Producer',
    'sw_mac': '00:00:00:00:01:01',
    'sw_port': 4,
    'wired-rx_bytes': 1234000000,
    'wired-tx_bytes': 5678000000
}
CLOUDKEY = {
    'hostname': 'client_1',
    'ip': 'mock-host',
    'is_wired': True,
    'mac': '10:00:00:00:00:01',
    'name': 'Cloud key',
    'oui': 'Producer',
    'sw_mac': '00:00:00:00:01:01',
    'sw_port': 1,
    'wired-rx_bytes': 1234000000,
    'wired-tx_bytes': 5678000000
}
POE_SWITCH_CLIENTS = [
    {
        'hostname': 'client_1',
        'ip': '10.0.0.1',
        'is_wired': True,
        'mac': '00:00:00:00:00:01',
        'name': 'POE Client 1',
        'oui': 'Producer',
        'sw_mac': '00:00:00:00:01:01',
        'sw_port': 1,
        'wired-rx_bytes': 1234000000,
        'wired-tx_bytes': 5678000000
    },
    {
        'hostname': 'client_2',
        'ip': '10.0.0.2',
        'is_wired': True,
        'mac': '00:00:00:00:00:02',
        'name': 'POE Client 2',
        'oui': 'Producer',
        'sw_mac': '00:00:00:00:01:01',
        'sw_port': 1,
        'wired-rx_bytes': 1234000000,
        'wired-tx_bytes': 5678000000
    }
]

DEVICE_1 = {
    'device_id': 'mock-id',
    'ip': '10.0.1.1',
    'mac': '00:00:00:00:01:01',
    'type': 'usw',
    'name': 'mock-name',
    'portconf_id': '',
    'port_table': [
        {
            'media': 'GE',
            'name': 'Port 1',
            'port_idx': 1,
            'poe_class': 'Class 4',
            'poe_enable': True,
            'poe_mode': 'auto',
            'poe_power': '2.56',
            'poe_voltage': '53.40',
            'portconf_id': '1a1',
            'port_poe': True,
            'up': True
        },
        {
            'media': 'GE',
            'name': 'Port 2',
            'port_idx': 2,
            'poe_class': 'Class 4',
            'poe_enable': True,
            'poe_mode': 'auto',
            'poe_power': '2.56',
            'poe_voltage': '53.40',
            'portconf_id': '1a2',
            'port_poe': True,
            'up': True
        },
        {
            'media': 'GE',
            'name': 'Port 3',
            'port_idx': 3,
            'poe_class': 'Unknown',
            'poe_enable': False,
            'poe_mode': 'off',
            'poe_power': '0.00',
            'poe_voltage': '0.00',
            'portconf_id': '1a3',
            'port_poe': False,
            'up': True
        },
        {
            'media': 'GE',
            'name': 'Port 4',
            'port_idx': 4,
            'poe_class': 'Unknown',
            'poe_enable': False,
            'poe_mode': 'auto',
            'poe_power': '0.00',
            'poe_voltage': '0.00',
            'portconf_id': '1a4',
            'port_poe': True,
            'up': True
        }
    ]
}

CONTROLLER_DATA = {
    unifi.CONF_HOST: 'mock-host',
    unifi.CONF_USERNAME: 'mock-user',
    unifi.CONF_PASSWORD: 'mock-pswd',
    unifi.CONF_PORT: 1234,
    unifi.CONF_SITE_ID: 'mock-site',
    unifi.CONF_VERIFY_SSL: True
}

ENTRY_CONFIG = {
    unifi.CONF_CONTROLLER: CONTROLLER_DATA,
    unifi.CONF_POE_CONTROL: True
}

CONTROLLER_ID = unifi.CONTROLLER_ID.format(host='mock-host', site='mock-site')


@pytest.fixture
def mock_controller(hass):
    """Mock a UniFi Controller."""
    controller = Mock(
        available=True,
        api=Mock(),
        spec=unifi.UniFiController
    )
    controller.mac = '10:00:00:00:00:01'
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
    await hass.config_entries.async_forward_entry_setup(config_entry, 'switch')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a bridge."""
    assert await async_setup_component(hass, switch.DOMAIN, {
        'switch': {
            'platform': 'unifi'
        }
    }) is True
    assert unifi.DOMAIN not in hass.data


async def test_no_clients(hass, mock_controller):
    """Test the update_clients function when no clients are found."""
    mock_controller.mock_client_responses.append({})
    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 2
    assert not hass.states.async_all()


async def test_controller_not_client(hass, mock_controller):
    """Test that the controller doesn't become a switch."""
    mock_controller.mock_client_responses.append([CLOUDKEY])
    mock_controller.mock_device_responses.append([DEVICE_1])
    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 2
    assert not hass.states.async_all()
    cloudkey = hass.states.get('switch.cloud_key')
    assert cloudkey is None


async def test_switches(hass, mock_controller):
    """Test the update_items function with some lights."""
    mock_controller.mock_client_responses.append([CLIENT_1, CLIENT_4])
    mock_controller.mock_device_responses.append([DEVICE_1])
    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 2
    # 1 All Lights group, 2 lights
    assert len(hass.states.async_all()) == 2

    switch_1 = hass.states.get('switch.client_1')
    assert switch_1 is not None
    assert switch_1.state == 'on'
    assert switch_1.attributes['power'] == '2.56'
    assert switch_1.attributes['received'] == 1234
    assert switch_1.attributes['sent'] == 5678
    assert switch_1.attributes['switch'] == '00:00:00:00:01:01'
    assert switch_1.attributes['port'] == 1
    assert switch_1.attributes['poe_mode'] == 'auto'

    switch = hass.states.get('switch.client_4')
    assert switch is None


async def test_new_client_discovered(hass, mock_controller):
    """Test if 2nd update has a new client."""
    mock_controller.mock_client_responses.append([CLIENT_1])
    mock_controller.mock_device_responses.append([DEVICE_1])

    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 2
    assert len(hass.states.async_all()) == 2

    mock_controller.mock_client_responses.append([CLIENT_1, CLIENT_2])
    mock_controller.mock_device_responses.append([DEVICE_1])

    # Calling a service will trigger the updates to run
    await hass.services.async_call('switch', 'turn_off', {
        'entity_id': 'switch.client_1'
    }, blocking=True)
    # 2x light update, 1 turn on request
    assert len(mock_controller.mock_requests) == 5
    assert len(hass.states.async_all()) == 3

    switch = hass.states.get('switch.client_2')
    assert switch is not None
    assert switch.state == 'on'


async def test_failed_update_successful_login(hass, mock_controller):
    """Running update can login when requested."""
    mock_controller.available = False
    mock_controller.api.clients.update = Mock()
    mock_controller.api.clients.update.side_effect = aiounifi.LoginRequired
    mock_controller.api.login = Mock()
    mock_controller.api.login.return_value = mock_coro()

    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 0

    assert mock_controller.available is True


async def test_failed_update_failed_login(hass, mock_controller):
    """Running update can handle a failed login."""
    mock_controller.api.clients.update = Mock()
    mock_controller.api.clients.update.side_effect = aiounifi.LoginRequired
    mock_controller.api.login = Mock()
    mock_controller.api.login.side_effect = aiounifi.AiounifiException

    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 0

    assert mock_controller.available is False


async def test_failed_update_unreachable_controller(hass, mock_controller):
    """Running update can handle a unreachable controller."""
    mock_controller.mock_client_responses.append([CLIENT_1, CLIENT_2])
    mock_controller.mock_device_responses.append([DEVICE_1])

    await setup_controller(hass, mock_controller)

    mock_controller.api.clients.update = Mock()
    mock_controller.api.clients.update.side_effect = aiounifi.AiounifiException

    # Calling a service will trigger the updates to run
    await hass.services.async_call('switch', 'turn_off', {
        'entity_id': 'switch.client_1'
    }, blocking=True)
    # 2x light update, 1 turn on request
    assert len(mock_controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 3

    assert mock_controller.available is False


async def test_ignore_multiple_poe_clients_on_same_port(hass, mock_controller):
    """Ignore when there are multiple POE driven clients on same port.

    If there is a non-UniFi switch powered by POE,
    clients will be transparently marked as having POE as well.
    """
    mock_controller.mock_client_responses.append(POE_SWITCH_CLIENTS)
    mock_controller.mock_device_responses.append([DEVICE_1])
    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 2
    # 1 All Lights group, 2 lights
    assert len(hass.states.async_all()) == 0

    switch_1 = hass.states.get('switch.client_1')
    switch_2 = hass.states.get('switch.client_2')
    assert switch_1 is None
    assert switch_2 is None
