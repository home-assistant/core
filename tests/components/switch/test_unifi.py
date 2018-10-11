"""UniFi POE control platform tests."""
import asyncio
from collections import deque
import logging
from unittest.mock import Mock, patch

import aiounifi
from aiounifi.clients import Clients
from aiounifi.devices import Devices
import pytest

from homeassistant import config_entries
from homeassistant.components import unifi
import homeassistant.components.switch.unifi as unifi_switch

from tests.common import mock_coro

CLIENT_1 = {
    'hostname': 'client_1',
    'ip': '10.0.0.1',
    'is_wired': True,
    'mac': '00:00:00:00:00:01',
    'name': 'Client 1',
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
    'name': 'Client 2',
    'oui': 'Producer',
    'sw_mac': '00:00:00:00:01:01',
    'sw_port': 2,
    'wired-rx_bytes': 1234000000,
    'wired-tx_bytes': 5678000000
}

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
            'poe_class': 'Unkown',
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
            'poe_class': 'Unkown',
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


async def test_no_clients(hass, mock_controller):
    """Test the update_clients function when no clients are found."""
    mock_controller.mock_client_responses.append({})
    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 2
    assert not hass.states.async_all()


async def test_switches(hass, mock_controller):
    """Test the update_items function with some lights."""
    mock_controller.mock_client_responses.append([CLIENT_1])
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


async def test_new_client_discovered(hass, mock_controller):
    """Test if 2nd update has a new client."""
    mock_controller.mock_client_responses.append([CLIENT_1])
    mock_controller.mock_device_responses.append([DEVICE_1])

    await setup_controller(hass, mock_controller)
    assert len(mock_controller.mock_requests) == 2
    assert len(hass.states.async_all()) == 2

    new_client_response = [CLIENT_1, CLIENT_2]

    mock_controller.mock_client_responses.append(new_client_response)
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



# client

# client go off

# client come back

# client come back on different position

# async def test_controller_request_update():
#     """First request returns result on success."""
#     hass = Mock()
#     entry = Mock()
#     entry.data = ENTRY_CONFIG
#     api = Mock()
#     api.initialize.return_value = mock_coro(True)
#     update = Mock()

#     unifi_controller = controller.UniFiController(hass, entry)

#     with patch.object(controller, 'get_controller',
#                       return_value=mock_coro(api)), \
#         patch.object(controller.UniFiController, 'async_update',
#                      return_value=mock_coro(update)):
#         assert await unifi_controller.async_setup() is True
#         assert await unifi_controller.request_update() == update


# async def test_controller_parallell_request_update():
#     """Second request gets queued and returns result on success."""
#     hass = Mock()
#     entry = Mock()
#     entry.data = ENTRY_CONFIG
#     api = Mock()
#     api.initialize.return_value = mock_coro(True)
#     update = Mock()

#     unifi_controller = controller.UniFiController(hass, entry)
#     unifi_controller.progress = mock_coro(update)

#     with patch.object(controller, 'get_controller',
#                       return_value=mock_coro(api)), \
#         patch.object(controller.UniFiController, 'async_update',
#                      return_value=mock_coro()):
#         assert await unifi_controller.async_setup() is True
#         assert await unifi_controller.request_update() == update


# async def test_controller_update():
#     """Running update refreshes data and keeps controller available."""
#     hass = Mock()
#     entry = Mock()
#     entry.data = ENTRY_CONFIG
#     api = Mock()
#     api.initialize.return_value = mock_coro(True)
#     api.clients.update.return_value = mock_coro(True)
#     api.devices.update.return_value = mock_coro(True)

#     unifi_controller = controller.UniFiController(hass, entry)

#     with patch.object(controller, 'get_controller',
#                       return_value=mock_coro(api)):
#         assert await unifi_controller.async_setup() is True
#         await unifi_controller.async_update()

#     assert unifi_controller.available is True


# async def test_controller_update_make_available():
#     """Running update refreshes data and makes controller available."""
#     hass = Mock()
#     entry = Mock()
#     entry.data = ENTRY_CONFIG
#     api = Mock()
#     api.initialize.return_value = mock_coro(True)
#     api.clients.update.return_value = mock_coro(True)
#     api.devices.update.return_value = mock_coro(True)

#     unifi_controller = controller.UniFiController(hass, entry)
#     unifi_controller.available = False

#     with patch.object(controller, 'get_controller',
#                       return_value=mock_coro(api)):
#         assert await unifi_controller.async_setup() is True
#         await unifi_controller.async_update()

#     assert unifi_controller.available is True


# async def test_controller_failed_update_successful_login():
#     """Running update can login when requested."""
#     import aiounifi
#     hass = Mock()
#     entry = Mock()
#     entry.data = ENTRY_CONFIG
#     api = Mock()
#     api.initialize.return_value = mock_coro(True)
#     api.clients.update.side_effect = aiounifi.LoginRequired
#     api.login = Mock()
#     api.login.return_value = mock_coro()

#     unifi_controller = controller.UniFiController(hass, entry)

#     with patch.object(controller, 'get_controller',
#                       return_value=mock_coro(api)):

#         assert await unifi_controller.async_setup() is True
#         await unifi_controller.async_update()

#     assert unifi_controller.available is True


# async def test_controller_failed_update_failed_login():
#     """Failing to login sets controller to unavailable."""
#     import aiounifi
#     hass = Mock()
#     entry = Mock()
#     entry.data = ENTRY_CONFIG
#     api = Mock()
#     api.initialize.return_value = mock_coro(True)
#     api.clients.update.side_effect = aiounifi.LoginRequired
#     api.login = Mock()
#     api.login.side_effect = aiounifi.AiounifiException

#     unifi_controller = controller.UniFiController(hass, entry)

#     with patch.object(controller, 'get_controller',
#                       return_value=mock_coro(api)):

#         assert await unifi_controller.async_setup() is True
#         await unifi_controller.async_update()

#     assert unifi_controller.available is False


# async def test_controller_failed_update_controller_unavailable():
#     """Fail update sets controller to unavailable."""
#     import aiounifi
#     hass = Mock()
#     entry = Mock()
#     entry.data = ENTRY_CONFIG
#     api = Mock()
#     api.initialize.return_value = mock_coro(True)
#     api.clients.update.side_effect = aiounifi.AiounifiException

#     unifi_controller = unifi.controller.UniFiController(hass, entry)

#     with patch.object(unifi.controller, 'get_controller',
#                       return_value=mock_coro(api)):

#         assert await unifi_controller.async_setup() is True
#         await unifi_controller.async_update()

#     assert unifi_controller.available is False
