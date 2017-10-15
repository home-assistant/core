"""Test the cloud.iot module."""
import asyncio
from unittest.mock import patch, MagicMock, PropertyMock

from aiohttp import WSMsgType, client_exceptions
import pytest

from homeassistant.components.cloud import iot, auth_api
from tests.common import mock_coro


@pytest.fixture
def mock_client():
    """Mock the IoT client."""
    client = MagicMock()
    type(client).closed = PropertyMock(side_effect=[False, True])

    with patch('asyncio.sleep'), \
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


@asyncio.coroutine
def test_cloud_calling_handler(mock_client, mock_handle_message):
    """Test we call handle message with correct info."""
    cloud = MagicMock()
    conn = iot.CloudIoT(cloud)
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

    assert p_hass is cloud.hass
    assert p_cloud is cloud
    assert handler_name == 'test-handler'
    assert payload == 'test-payload'

    # Check that we forwarded response from handler to cloud
    assert len(mock_client.send_json.mock_calls) == 1
    assert mock_client.send_json.mock_calls[0][1][0] == {
        'msgid': 'test-msg-id',
        'payload': 'response'
    }


@asyncio.coroutine
def test_connection_msg_for_unknown_handler(mock_client):
    """Test a msg for an unknown handler."""
    cloud = MagicMock()
    conn = iot.CloudIoT(cloud)
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
def test_connection_msg_for_handler_raising(mock_client, mock_handle_message):
    """Test we sent error when handler raises exception."""
    cloud = MagicMock()
    conn = iot.CloudIoT(cloud)
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
def test_handling_core_messages(hass):
    """Test handling core messages."""
    cloud = MagicMock()
    cloud.logout.return_value = mock_coro()
    yield from iot.async_handle_cloud(hass, cloud, {
        'action': 'logout',
        'reason': 'Logged in at two places.'
    })
    assert len(cloud.logout.mock_calls) == 1


@asyncio.coroutine
def test_cloud_getting_disconnected_by_server(mock_client, caplog):
    """Test server disconnecting instance."""
    cloud = MagicMock()
    conn = iot.CloudIoT(cloud)
    mock_client.receive.return_value = mock_coro(MagicMock(
        type=WSMsgType.CLOSING,
    ))

    yield from conn.connect()

    assert 'Connection closed: Closed by server' in caplog.text
    assert 'connect' in str(cloud.hass.async_add_job.mock_calls[-1][1][0])


@asyncio.coroutine
def test_cloud_receiving_bytes(mock_client, caplog):
    """Test server disconnecting instance."""
    cloud = MagicMock()
    conn = iot.CloudIoT(cloud)
    mock_client.receive.return_value = mock_coro(MagicMock(
        type=WSMsgType.BINARY,
    ))

    yield from conn.connect()

    assert 'Connection closed: Received non-Text message' in caplog.text
    assert 'connect' in str(cloud.hass.async_add_job.mock_calls[-1][1][0])


@asyncio.coroutine
def test_cloud_sending_invalid_json(mock_client, caplog):
    """Test cloud sending invalid JSON."""
    cloud = MagicMock()
    conn = iot.CloudIoT(cloud)
    mock_client.receive.return_value = mock_coro(MagicMock(
        type=WSMsgType.TEXT,
        json=MagicMock(side_effect=ValueError)
    ))

    yield from conn.connect()

    assert 'Connection closed: Received invalid JSON.' in caplog.text
    assert 'connect' in str(cloud.hass.async_add_job.mock_calls[-1][1][0])


@asyncio.coroutine
def test_cloud_check_token_raising(mock_client, caplog):
    """Test cloud sending invalid JSON."""
    cloud = MagicMock()
    conn = iot.CloudIoT(cloud)
    mock_client.receive.side_effect = auth_api.CloudError

    yield from conn.connect()

    assert 'Unable to connect: Unable to refresh token.' in caplog.text
    assert 'connect' in str(cloud.hass.async_add_job.mock_calls[-1][1][0])


@asyncio.coroutine
def test_cloud_connect_invalid_auth(mock_client, caplog):
    """Test invalid auth detected by server."""
    cloud = MagicMock()
    conn = iot.CloudIoT(cloud)
    mock_client.receive.side_effect = \
        client_exceptions.WSServerHandshakeError(None, None, code=401)

    yield from conn.connect()

    assert 'Connection closed: Invalid auth.' in caplog.text


@asyncio.coroutine
def test_cloud_unable_to_connect(mock_client, caplog):
    """Test unable to connect error."""
    cloud = MagicMock()
    conn = iot.CloudIoT(cloud)
    mock_client.receive.side_effect = client_exceptions.ClientError(None, None)

    yield from conn.connect()

    assert 'Unable to connect:' in caplog.text


@asyncio.coroutine
def test_cloud_random_exception(mock_client, caplog):
    """Test random exception."""
    cloud = MagicMock()
    conn = iot.CloudIoT(cloud)
    mock_client.receive.side_effect = Exception

    yield from conn.connect()

    assert 'Unexpected error' in caplog.text
