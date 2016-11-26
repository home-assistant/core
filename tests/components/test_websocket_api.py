import asyncio
from unittest.mock import patch

from aiohttp import WSMsgType
from async_timeout import timeout
import pytest

from homeassistant.core import callback
from homeassistant.components import websocket_api as wapi

from tests.common import mock_http_component_app

API_PASSWORD = 'test1234'


@pytest.fixture
def websocket_client(loop, hass, test_client):
    """Websocket client fixture connected to websocket server."""
    websocket_app = mock_http_component_app(hass)
    wapi.WebsocketAPIView().register(websocket_app.router)

    client = loop.run_until_complete(test_client(websocket_app))
    ws = loop.run_until_complete(client.ws_connect(wapi.URL))

    auth_ok = loop.run_until_complete(ws.receive_json())
    assert auth_ok['type'] == wapi.TYPE_AUTH_OK

    yield ws

    if not ws.closed:
        loop.run_until_complete(ws.close())


@pytest.fixture
def no_auth_websocket_client(hass, loop, test_client):
    """Websocket connection that requires authentication."""
    websocket_app = mock_http_component_app(hass, API_PASSWORD)
    wapi.WebsocketAPIView().register(websocket_app.router)

    client = loop.run_until_complete(test_client(websocket_app))
    ws = loop.run_until_complete(client.ws_connect(wapi.URL))

    auth_ok = loop.run_until_complete(ws.receive_json())
    assert auth_ok['type'] == wapi.TYPE_AUTH_REQUIRED

    yield ws

    if not ws.closed:
        loop.run_until_complete(ws.close())


@asyncio.coroutine
def test_auth_via_msg(no_auth_websocket_client):
    """Test authenticating."""
    no_auth_websocket_client.send_json({
        'type': wapi.TYPE_AUTH,
        'api_password': API_PASSWORD
    })

    msg = yield from no_auth_websocket_client.receive_json()

    assert msg['type'] == wapi.TYPE_AUTH_OK


@asyncio.coroutine
def test_auth_via_msg_incorrect_pass(no_auth_websocket_client):
    """Test authenticating."""
    no_auth_websocket_client.send_json({
        'type': wapi.TYPE_AUTH,
        'api_password': API_PASSWORD + 'wrong'
    })

    msg = yield from no_auth_websocket_client.receive_json()

    assert msg['type'] == wapi.TYPE_AUTH_INVALID
    assert msg['message'] == 'Invalid password'


@asyncio.coroutine
def test_pre_auth_only_auth_allowed(no_auth_websocket_client):
    """Verify that before authentication, only auth messages are allowed."""
    no_auth_websocket_client.send_json({
        'type': wapi.TYPE_CALL_SERVICE,
        'domain': 'domain_test',
        'service': 'test_service',
        'service_data': {
            'hello': 'world'
        }
    })

    msg = yield from no_auth_websocket_client.receive_json()

    assert msg['type'] == wapi.TYPE_AUTH_INVALID
    assert msg['message'].startswith('Message incorrectly formatted')


@asyncio.coroutine
def test_invalid_message_format(websocket_client):
    """Test sending invalid JSON."""
    websocket_client.send_json({'type': 5})

    msg = yield from websocket_client.receive_json()

    assert msg['type'] == wapi.TYPE_RESULT
    error = msg['error']
    assert error['code'] == wapi.ERR_INVALID_FORMAT
    assert error['message'].startswith('Message incorrectly formatted')


@asyncio.coroutine
def test_invalid_json(websocket_client):
    """Test sending invalid JSON."""
    websocket_client.send_str('this is not JSON')

    msg = yield from websocket_client.receive()

    assert msg.type == WSMsgType.close


@asyncio.coroutine
def test_quiting_hass(hass, websocket_client):
    """Test sending invalid JSON."""
    with patch.object(hass.loop, 'stop'):
        yield from hass.async_stop()

    msg = yield from websocket_client.receive()

    assert msg.type == WSMsgType.CLOSE


@asyncio.coroutine
def test_call_service(hass, websocket_client):
    """Test call service command."""
    calls = []

    @callback
    def service_call(call):
        calls.append(call)

    hass.services.async_register('domain_test', 'test_service', service_call)

    websocket_client.send_json({
        'id': 5,
        'type': wapi.TYPE_CALL_SERVICE,
        'domain': 'domain_test',
        'service': 'test_service',
        'service_data': {
            'hello': 'world'
        }
    })

    msg = yield from websocket_client.receive_json()
    assert msg['id'] == 5
    assert msg['type'] == wapi.TYPE_RESULT
    assert msg['success']

    assert len(calls) == 1
    call = calls[0]

    assert call.domain == 'domain_test'
    assert call.service == 'test_service'
    assert call.data == {'hello': 'world'}


@asyncio.coroutine
def test_call_listen_event_match_event_type(hass, websocket_client):
    """Test call service command."""
    init_count = sum(hass.bus.async_listeners().values())

    websocket_client.send_json({
        'id': 5,
        'type': wapi.TYPE_LISTEN_EVENT,
        'event_type': 'test_event'
    })

    msg = yield from websocket_client.receive_json()
    assert msg['id'] == 5
    assert msg['type'] == wapi.TYPE_RESULT
    assert msg['success']

    # Verify we have a new listener
    assert sum(hass.bus.async_listeners().values()) == init_count + 1

    hass.bus.async_fire('ignore_event')
    hass.bus.async_fire('test_event', {'hello': 'world'})
    hass.bus.async_fire('ignore_event')

    with timeout(3, loop=hass.loop):
        msg = yield from websocket_client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == wapi.TYPE_EVENT
    event = msg['event']

    assert event['event_type'] == 'test_event'
    assert event['data'] == {'hello': 'world'}
    assert event['origin'] == 'LOCAL'

    yield from websocket_client.close()

    # Check our listener got unsubscribed
    assert sum(hass.bus.async_listeners().values()) == init_count
