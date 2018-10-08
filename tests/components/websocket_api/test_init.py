"""Tests for the Home Assistant Websocket API."""
import asyncio
from unittest.mock import patch, Mock

from aiohttp import WSMsgType
import pytest

from homeassistant.components.websocket_api import const, commands, messages


@pytest.fixture
def mock_low_queue():
    """Mock a low queue."""
    with patch('homeassistant.components.websocket_api.http.MAX_PENDING_MSG',
               5):
        yield


@asyncio.coroutine
def test_invalid_message_format(websocket_client):
    """Test sending invalid JSON."""
    yield from websocket_client.send_json({'type': 5})

    msg = yield from websocket_client.receive_json()

    assert msg['type'] == const.TYPE_RESULT
    error = msg['error']
    assert error['code'] == const.ERR_INVALID_FORMAT
    assert error['message'].startswith('Message incorrectly formatted')


@asyncio.coroutine
def test_invalid_json(websocket_client):
    """Test sending invalid JSON."""
    yield from websocket_client.send_str('this is not JSON')

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
def test_pending_msg_overflow(hass, mock_low_queue, websocket_client):
    """Test get_panels command."""
    for idx in range(10):
        yield from websocket_client.send_json({
            'id': idx + 1,
            'type': commands.TYPE_PING,
        })
    msg = yield from websocket_client.receive()
    assert msg.type == WSMsgType.close


@asyncio.coroutine
def test_unknown_command(websocket_client):
    """Test get_panels command."""
    yield from websocket_client.send_json({
        'id': 5,
        'type': 'unknown_command',
    })

    msg = yield from websocket_client.receive_json()
    assert not msg['success']
    assert msg['error']['code'] == const.ERR_UNKNOWN_COMMAND


async def test_handler_failing(hass, websocket_client):
    """Test a command that raises."""
    hass.components.websocket_api.async_register_command(
        'bla', Mock(side_effect=TypeError),
        messages.BASE_COMMAND_MESSAGE_SCHEMA.extend({'type': 'bla'}))
    await websocket_client.send_json({
        'id': 5,
        'type': 'bla',
    })

    msg = await websocket_client.receive_json()
    assert msg['id'] == 5
    assert msg['type'] == const.TYPE_RESULT
    assert not msg['success']
    assert msg['error']['code'] == const.ERR_UNKNOWN_ERROR
