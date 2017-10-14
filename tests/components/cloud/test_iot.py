"""Test the cloud.iot module."""
import asyncio
import json
from unittest.mock import patch, MagicMock, PropertyMock

from aiohttp import WSMsgType
import pytest

from homeassistant.components.cloud import iot
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
