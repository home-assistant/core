"""Test the cloud.iot module."""
import asyncio
from unittest.mock import patch, MagicMock, PropertyMock

from aiohttp import WSMsgType, client_exceptions, web
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components.cloud import (
    Cloud, iot, auth_api, MODE_DEV)
from homeassistant.components.cloud.const import (
    PREF_ENABLE_ALEXA, PREF_ENABLE_GOOGLE)
from tests.components.alexa import test_smart_home as test_alexa
from tests.common import mock_coro

from . import mock_cloud_prefs


@pytest.fixture
def mock_client():
    """Mock the IoT client."""
    client = MagicMock()
    type(client).closed = PropertyMock(side_effect=[False, True])

    # Trigger cancelled error to avoid reconnect.
    with patch('asyncio.sleep', side_effect=asyncio.CancelledError), \
            patch('homeassistant.components.cloud.iot'
                  '.async_get_clientsession') as session:
        session().ws_connect.return_value = mock_coro(client)
        yield client


@pytest.fixture
def mock_handle_message():
    """Mock handle message."""
    with patch('homeassistant.components.cloud.iot'
               '.async_handle_message') as mock:
        yield mock


@pytest.fixture
def mock_cloud():
    """Mock cloud class."""
    return MagicMock(subscription_expired=False)


@asyncio.coroutine
def test_cloud_calling_handler(mock_client, mock_handle_message, mock_cloud):
    """Test we call handle message with correct info."""
    conn = iot.CloudIoT(mock_cloud)
    mock_client.receive.return_value = mock_coro(MagicMock(
        type=WSMsgType.text,
        json=MagicMock(return_value={
            'msgid': 'test-msg-id',
            'handler': 'test-handler',
            'payload': 'test-payload'
        })
    ))
    mock_handle_message.return_value = mock_coro('response')
    mock_client.send_json.return_value = mock_coro(None)

    yield from conn.connect()

    # Check that we sent message to handler correctly
    assert len(mock_handle_message.mock_calls) == 1
    p_hass, p_cloud, handler_name, payload = \
        mock_handle_message.mock_calls[0][1]

    assert p_hass is mock_cloud.hass
    assert p_cloud is mock_cloud
    assert handler_name == 'test-handler'
    assert payload == 'test-payload'

    # Check that we forwarded response from handler to cloud
    assert len(mock_client.send_json.mock_calls) == 1
    assert mock_client.send_json.mock_calls[0][1][0] == {
        'msgid': 'test-msg-id',
        'payload': 'response'
    }


@asyncio.coroutine
def test_connection_msg_for_unknown_handler(mock_client, mock_cloud):
    """Test a msg for an unknown handler."""
    conn = iot.CloudIoT(mock_cloud)
    mock_client.receive.return_value = mock_coro(MagicMock(
        type=WSMsgType.text,
        json=MagicMock(return_value={
            'msgid': 'test-msg-id',
            'handler': 'non-existing-handler',
            'payload': 'test-payload'
        })
    ))
    mock_client.send_json.return_value = mock_coro(None)

    yield from conn.connect()

    # Check that we sent the correct error
    assert len(mock_client.send_json.mock_calls) == 1
    assert mock_client.send_json.mock_calls[0][1][0] == {
        'msgid': 'test-msg-id',
        'error': 'unknown-handler',
    }


@asyncio.coroutine
def test_connection_msg_for_handler_raising(mock_client, mock_handle_message,
                                            mock_cloud):
    """Test we sent error when handler raises exception."""
    conn = iot.CloudIoT(mock_cloud)
    mock_client.receive.return_value = mock_coro(MagicMock(
        type=WSMsgType.text,
        json=MagicMock(return_value={
            'msgid': 'test-msg-id',
            'handler': 'test-handler',
            'payload': 'test-payload'
        })
    ))
    mock_handle_message.side_effect = Exception('Broken')
    mock_client.send_json.return_value = mock_coro(None)

    yield from conn.connect()

    # Check that we sent the correct error
    assert len(mock_client.send_json.mock_calls) == 1
    assert mock_client.send_json.mock_calls[0][1][0] == {
        'msgid': 'test-msg-id',
        'error': 'exception',
    }


@asyncio.coroutine
def test_handler_forwarding():
    """Test we forward messages to correct handler."""
    handler = MagicMock()
    handler.return_value = mock_coro()
    hass = object()
    cloud = object()
    with patch.dict(iot.HANDLERS, {'test': handler}):
        yield from iot.async_handle_message(
            hass, cloud, 'test', 'payload')

    assert len(handler.mock_calls) == 1
    r_hass, r_cloud, payload = handler.mock_calls[0][1]
    assert r_hass is hass
    assert r_cloud is cloud
    assert payload == 'payload'


@asyncio.coroutine
def test_handling_core_messages(hass, mock_cloud):
    """Test handling core messages."""
    mock_cloud.logout.return_value = mock_coro()
    yield from iot.async_handle_cloud(hass, mock_cloud, {
        'action': 'logout',
        'reason': 'Logged in at two places.'
    })
    assert len(mock_cloud.logout.mock_calls) == 1


@asyncio.coroutine
def test_cloud_getting_disconnected_by_server(mock_client, caplog, mock_cloud):
    """Test server disconnecting instance."""
    conn = iot.CloudIoT(mock_cloud)
    mock_client.receive.return_value = mock_coro(MagicMock(
        type=WSMsgType.CLOSING,
    ))

    with patch('asyncio.sleep', side_effect=[None, asyncio.CancelledError]):
        yield from conn.connect()

    assert 'Connection closed' in caplog.text


@asyncio.coroutine
def test_cloud_receiving_bytes(mock_client, caplog, mock_cloud):
    """Test server disconnecting instance."""
    conn = iot.CloudIoT(mock_cloud)
    mock_client.receive.return_value = mock_coro(MagicMock(
        type=WSMsgType.BINARY,
    ))

    yield from conn.connect()

    assert 'Connection closed: Received non-Text message' in caplog.text


@asyncio.coroutine
def test_cloud_sending_invalid_json(mock_client, caplog, mock_cloud):
    """Test cloud sending invalid JSON."""
    conn = iot.CloudIoT(mock_cloud)
    mock_client.receive.return_value = mock_coro(MagicMock(
        type=WSMsgType.TEXT,
        json=MagicMock(side_effect=ValueError)
    ))

    yield from conn.connect()

    assert 'Connection closed: Received invalid JSON.' in caplog.text


@asyncio.coroutine
def test_cloud_check_token_raising(mock_client, caplog, mock_cloud):
    """Test cloud unable to check token."""
    conn = iot.CloudIoT(mock_cloud)
    mock_cloud.hass.async_add_job.side_effect = auth_api.CloudError("BLA")

    yield from conn.connect()

    assert 'Unable to refresh token: BLA' in caplog.text


@asyncio.coroutine
def test_cloud_connect_invalid_auth(mock_client, caplog, mock_cloud):
    """Test invalid auth detected by server."""
    conn = iot.CloudIoT(mock_cloud)
    mock_client.receive.side_effect = \
        client_exceptions.WSServerHandshakeError(None, None, status=401)

    yield from conn.connect()

    assert 'Connection closed: Invalid auth.' in caplog.text


@asyncio.coroutine
def test_cloud_unable_to_connect(mock_client, caplog, mock_cloud):
    """Test unable to connect error."""
    conn = iot.CloudIoT(mock_cloud)
    mock_client.receive.side_effect = client_exceptions.ClientError(None, None)

    yield from conn.connect()

    assert 'Unable to connect:' in caplog.text


@asyncio.coroutine
def test_cloud_random_exception(mock_client, caplog, mock_cloud):
    """Test random exception."""
    conn = iot.CloudIoT(mock_cloud)
    mock_client.receive.side_effect = Exception

    yield from conn.connect()

    assert 'Unexpected error' in caplog.text


@asyncio.coroutine
def test_refresh_token_before_expiration_fails(hass, mock_cloud):
    """Test that we don't connect if token is expired."""
    mock_cloud.subscription_expired = True
    mock_cloud.hass = hass
    conn = iot.CloudIoT(mock_cloud)

    with patch('homeassistant.components.cloud.auth_api.check_token',
               return_value=mock_coro()) as mock_check_token, \
            patch.object(hass.components.persistent_notification,
                         'async_create') as mock_create:
        yield from conn.connect()

    assert len(mock_check_token.mock_calls) == 1
    assert len(mock_create.mock_calls) == 1


@asyncio.coroutine
def test_handler_alexa(hass):
    """Test handler Alexa."""
    hass.states.async_set(
        'switch.test', 'on', {'friendly_name': "Test switch"})
    hass.states.async_set(
        'switch.test2', 'on', {'friendly_name': "Test switch 2"})

    with patch('homeassistant.components.cloud.Cloud.async_start',
               return_value=mock_coro()):
        setup = yield from async_setup_component(hass, 'cloud', {
            'cloud': {
                'alexa': {
                    'filter': {
                        'exclude_entities': 'switch.test2'
                    },
                    'entity_config': {
                        'switch.test': {
                            'name': 'Config name',
                            'description': 'Config description',
                            'display_categories': 'LIGHT'
                        }
                    }
                }
            }
        })
        assert setup

    mock_cloud_prefs(hass)

    resp = yield from iot.async_handle_alexa(
        hass, hass.data['cloud'],
        test_alexa.get_new_request('Alexa.Discovery', 'Discover'))

    endpoints = resp['event']['payload']['endpoints']

    assert len(endpoints) == 1
    device = endpoints[0]

    assert device['description'] == 'Config description'
    assert device['friendlyName'] == 'Config name'
    assert device['displayCategories'] == ['LIGHT']
    assert device['manufacturerName'] == 'Home Assistant'


@asyncio.coroutine
def test_handler_alexa_disabled(hass, mock_cloud_fixture):
    """Test handler Alexa when user has disabled it."""
    mock_cloud_fixture[PREF_ENABLE_ALEXA] = False

    resp = yield from iot.async_handle_alexa(
        hass, hass.data['cloud'],
        test_alexa.get_new_request('Alexa.Discovery', 'Discover'))

    assert resp['event']['header']['namespace'] == 'Alexa'
    assert resp['event']['header']['name'] == 'ErrorResponse'
    assert resp['event']['payload']['type'] == 'BRIDGE_UNREACHABLE'


@asyncio.coroutine
def test_handler_google_actions(hass):
    """Test handler Google Actions."""
    hass.states.async_set(
        'switch.test', 'on', {'friendly_name': "Test switch"})
    hass.states.async_set(
        'switch.test2', 'on', {'friendly_name': "Test switch 2"})
    hass.states.async_set(
        'group.all_locks', 'on', {'friendly_name': "Evil locks"})

    with patch('homeassistant.components.cloud.Cloud.async_start',
               return_value=mock_coro()):
        setup = yield from async_setup_component(hass, 'cloud', {
            'cloud': {
                'google_actions': {
                    'filter': {
                        'exclude_entities': 'switch.test2'
                    },
                    'entity_config': {
                        'switch.test': {
                            'name': 'Config name',
                            'aliases': 'Config alias',
                            'room': 'living room'
                        }
                    }
                }
            }
        })
        assert setup

    mock_cloud_prefs(hass)

    reqid = '5711642932632160983'
    data = {'requestId': reqid, 'inputs': [{'intent': 'action.devices.SYNC'}]}

    with patch('homeassistant.components.cloud.Cloud._decode_claims',
               return_value={'cognito:username': 'myUserName'}):
        resp = yield from iot.async_handle_google_actions(
            hass, hass.data['cloud'], data)

    assert resp['requestId'] == reqid
    payload = resp['payload']

    assert payload['agentUserId'] == 'myUserName'

    devices = payload['devices']
    assert len(devices) == 1

    device = devices[0]
    assert device['id'] == 'switch.test'
    assert device['name']['name'] == 'Config name'
    assert device['name']['nicknames'] == ['Config alias']
    assert device['type'] == 'action.devices.types.SWITCH'
    assert device['roomHint'] == 'living room'


async def test_handler_google_actions_disabled(hass, mock_cloud_fixture):
    """Test handler Google Actions when user has disabled it."""
    mock_cloud_fixture[PREF_ENABLE_GOOGLE] = False

    with patch('homeassistant.components.cloud.Cloud.async_start',
               return_value=mock_coro()):
        assert await async_setup_component(hass, 'cloud', {})

    reqid = '5711642932632160983'
    data = {'requestId': reqid, 'inputs': [{'intent': 'action.devices.SYNC'}]}

    resp = await iot.async_handle_google_actions(
        hass, hass.data['cloud'], data)

    assert resp['requestId'] == reqid
    assert resp['payload']['errorCode'] == 'deviceTurnedOff'


async def test_refresh_token_expired(hass):
    """Test handling Unauthenticated error raised if refresh token expired."""
    cloud = Cloud(hass, MODE_DEV, None, None)

    with patch('homeassistant.components.cloud.auth_api.check_token',
               side_effect=auth_api.Unauthenticated) as mock_check_token, \
            patch.object(hass.components.persistent_notification,
                         'async_create') as mock_create:
        await cloud.iot.connect()

    assert len(mock_check_token.mock_calls) == 1
    assert len(mock_create.mock_calls) == 1


async def test_webhook_msg(hass):
    """Test webhook msg."""
    cloud = Cloud(hass, MODE_DEV, None, None)
    await cloud.prefs.async_initialize()
    await cloud.prefs.async_update(cloudhooks={
        'hello': {
            'webhook_id': 'mock-webhook-id',
            'cloudhook_id': 'mock-cloud-id'
        }
    })

    received = []

    async def handler(hass, webhook_id, request):
        """Handle a webhook."""
        received.append(request)
        return web.json_response({'from': 'handler'})

    hass.components.webhook.async_register(
        'test', 'Test', 'mock-webhook-id', handler)

    response = await iot.async_handle_webhook(hass, cloud, {
        'cloudhook_id': 'mock-cloud-id',
        'body': '{"hello": "world"}',
        'headers': {
            'content-type': 'application/json'
        },
        'method': 'POST',
        'query': None,
    })

    assert response == {
        'status': 200,
        'body': '{"from": "handler"}',
        'headers': {
            'Content-Type': 'application/json'
        }
    }

    assert len(received) == 1
    assert await received[0].json() == {
        'hello': 'world'
    }


async def test_send_message_not_connected(mock_cloud):
    """Test sending a message that expects no answer."""
    cloud_iot = iot.CloudIoT(mock_cloud)

    with pytest.raises(iot.NotConnected):
        await cloud_iot.async_send_message('webhook', {'msg': 'yo'})


async def test_send_message_no_answer(mock_cloud):
    """Test sending a message that expects no answer."""
    cloud_iot = iot.CloudIoT(mock_cloud)
    cloud_iot.state = iot.STATE_CONNECTED
    cloud_iot.client = MagicMock(send_json=MagicMock(return_value=mock_coro()))

    await cloud_iot.async_send_message('webhook', {'msg': 'yo'},
                                       expect_answer=False)
    assert not cloud_iot._response_handler
    assert len(cloud_iot.client.send_json.mock_calls) == 1
    msg = cloud_iot.client.send_json.mock_calls[0][1][0]
    assert msg['handler'] == 'webhook'
    assert msg['payload'] == {'msg': 'yo'}


async def test_send_message_answer(loop, mock_cloud):
    """Test sending a message that expects no answer."""
    cloud_iot = iot.CloudIoT(mock_cloud)
    cloud_iot.state = iot.STATE_CONNECTED
    cloud_iot.client = MagicMock(send_json=MagicMock(return_value=mock_coro()))

    uuid = 5

    with patch('homeassistant.components.cloud.iot.uuid.uuid4',
               return_value=MagicMock(hex=uuid)):
        send_task = loop.create_task(cloud_iot.async_send_message(
            'webhook', {'msg': 'yo'}))
        await asyncio.sleep(0)

    assert len(cloud_iot.client.send_json.mock_calls) == 1
    assert len(cloud_iot._response_handler) == 1
    msg = cloud_iot.client.send_json.mock_calls[0][1][0]
    assert msg['handler'] == 'webhook'
    assert msg['payload'] == {'msg': 'yo'}

    cloud_iot._response_handler[uuid].set_result({'response': True})
    response = await send_task
    assert response == {'response': True}
