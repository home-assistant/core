"""Tests for WebSocket API commands."""
from unittest.mock import patch

from async_timeout import timeout

from homeassistant.core import callback
from homeassistant.components.websocket_api.const import URL
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH, TYPE_AUTH_OK, TYPE_AUTH_REQUIRED
)
from homeassistant.components.websocket_api import const, commands
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service

from . import API_PASSWORD


async def test_call_service(hass, websocket_client):
    """Test call service command."""
    calls = []

    @callback
    def service_call(call):
        calls.append(call)

    hass.services.async_register('domain_test', 'test_service', service_call)

    await websocket_client.send_json({
        'id': 5,
        'type': commands.TYPE_CALL_SERVICE,
        'domain': 'domain_test',
        'service': 'test_service',
        'service_data': {
            'hello': 'world'
        }
    })

    msg = await websocket_client.receive_json()
    assert msg['id'] == 5
    assert msg['type'] == const.TYPE_RESULT
    assert msg['success']

    assert len(calls) == 1
    call = calls[0]

    assert call.domain == 'domain_test'
    assert call.service == 'test_service'
    assert call.data == {'hello': 'world'}


async def test_subscribe_unsubscribe_events(hass, websocket_client):
    """Test subscribe/unsubscribe events command."""
    init_count = sum(hass.bus.async_listeners().values())

    await websocket_client.send_json({
        'id': 5,
        'type': commands.TYPE_SUBSCRIBE_EVENTS,
        'event_type': 'test_event'
    })

    msg = await websocket_client.receive_json()
    assert msg['id'] == 5
    assert msg['type'] == const.TYPE_RESULT
    assert msg['success']

    # Verify we have a new listener
    assert sum(hass.bus.async_listeners().values()) == init_count + 1

    hass.bus.async_fire('ignore_event')
    hass.bus.async_fire('test_event', {'hello': 'world'})
    hass.bus.async_fire('ignore_event')

    with timeout(3, loop=hass.loop):
        msg = await websocket_client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == commands.TYPE_EVENT
    event = msg['event']

    assert event['event_type'] == 'test_event'
    assert event['data'] == {'hello': 'world'}
    assert event['origin'] == 'LOCAL'

    await websocket_client.send_json({
        'id': 6,
        'type': commands.TYPE_UNSUBSCRIBE_EVENTS,
        'subscription': 5
    })

    msg = await websocket_client.receive_json()
    assert msg['id'] == 6
    assert msg['type'] == const.TYPE_RESULT
    assert msg['success']

    # Check our listener got unsubscribed
    assert sum(hass.bus.async_listeners().values()) == init_count


async def test_get_states(hass, websocket_client):
    """Test get_states command."""
    hass.states.async_set('greeting.hello', 'world')
    hass.states.async_set('greeting.bye', 'universe')

    await websocket_client.send_json({
        'id': 5,
        'type': commands.TYPE_GET_STATES,
    })

    msg = await websocket_client.receive_json()
    assert msg['id'] == 5
    assert msg['type'] == const.TYPE_RESULT
    assert msg['success']

    states = []
    for state in hass.states.async_all():
        state = state.as_dict()
        state['last_changed'] = state['last_changed'].isoformat()
        state['last_updated'] = state['last_updated'].isoformat()
        states.append(state)

    assert msg['result'] == states


async def test_get_services(hass, websocket_client):
    """Test get_services command."""
    await websocket_client.send_json({
        'id': 5,
        'type': commands.TYPE_GET_SERVICES,
    })

    msg = await websocket_client.receive_json()
    assert msg['id'] == 5
    assert msg['type'] == const.TYPE_RESULT
    assert msg['success']
    assert msg['result'] == hass.services.async_services()


async def test_get_config(hass, websocket_client):
    """Test get_config command."""
    await websocket_client.send_json({
        'id': 5,
        'type': commands.TYPE_GET_CONFIG,
    })

    msg = await websocket_client.receive_json()
    assert msg['id'] == 5
    assert msg['type'] == const.TYPE_RESULT
    assert msg['success']

    if 'components' in msg['result']:
        msg['result']['components'] = set(msg['result']['components'])
    if 'whitelist_external_dirs' in msg['result']:
        msg['result']['whitelist_external_dirs'] = \
            set(msg['result']['whitelist_external_dirs'])

    assert msg['result'] == hass.config.as_dict()


async def test_ping(websocket_client):
    """Test get_panels command."""
    await websocket_client.send_json({
        'id': 5,
        'type': commands.TYPE_PING,
    })

    msg = await websocket_client.receive_json()
    assert msg['id'] == 5
    assert msg['type'] == commands.TYPE_PONG


async def test_call_service_context_with_user(hass, aiohttp_client,
                                              hass_access_token):
    """Test that the user is set in the service call context."""
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    calls = async_mock_service(hass, 'domain_test', 'test_service')
    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        with patch('homeassistant.auth.AuthManager.active') as auth_active:
            auth_active.return_value = True
            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_REQUIRED

            await ws.send_json({
                'type': TYPE_AUTH,
                'access_token': hass_access_token
            })

            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_OK

        await ws.send_json({
            'id': 5,
            'type': commands.TYPE_CALL_SERVICE,
            'domain': 'domain_test',
            'service': 'test_service',
            'service_data': {
                'hello': 'world'
            }
        })

        msg = await ws.receive_json()
        assert msg['success']

        refresh_token = await hass.auth.async_validate_access_token(
            hass_access_token)

        assert len(calls) == 1
        call = calls[0]
        assert call.domain == 'domain_test'
        assert call.service == 'test_service'
        assert call.data == {'hello': 'world'}
        assert call.context.user_id == refresh_token.user.id


async def test_call_service_context_no_user(hass, aiohttp_client):
    """Test that connection without user sets context."""
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    calls = async_mock_service(hass, 'domain_test', 'test_service')
    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg['type'] == TYPE_AUTH_REQUIRED

        await ws.send_json({
            'type': TYPE_AUTH,
            'api_password': API_PASSWORD
        })

        auth_msg = await ws.receive_json()
        assert auth_msg['type'] == TYPE_AUTH_OK

        await ws.send_json({
            'id': 5,
            'type': commands.TYPE_CALL_SERVICE,
            'domain': 'domain_test',
            'service': 'test_service',
            'service_data': {
                'hello': 'world'
            }
        })

        msg = await ws.receive_json()
        assert msg['success']

        assert len(calls) == 1
        call = calls[0]
        assert call.domain == 'domain_test'
        assert call.service == 'test_service'
        assert call.data == {'hello': 'world'}
        assert call.context.user_id is None
