"""Test WebSocket Connection class."""
import asyncio
import logging

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import const


async def test_send_big_result(hass, websocket_client):
    """Test sending big results over the WS."""

    @websocket_api.websocket_command({"type": "big_result"})
    @websocket_api.async_response
    async def send_big_result(hass, connection, msg):
        await connection.send_big_result(msg["id"], {"big": "result"})

    hass.components.websocket_api.async_register_command(send_big_result)

    await websocket_client.send_json({"id": 5, "type": "big_result"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {"big": "result"}


async def test_exception_handling():
    """Test handling of exceptions."""
    send_messages = []
    conn = websocket_api.ActiveConnection(
        logging.getLogger(__name__), None, send_messages.append, None, None
    )

    for (exc, code, err) in (
        (exceptions.Unauthorized(), websocket_api.ERR_UNAUTHORIZED, "Unauthorized"),
        (
            vol.Invalid("Invalid something"),
            websocket_api.ERR_INVALID_FORMAT,
            "Invalid something. Got {'id': 5}",
        ),
        (asyncio.TimeoutError(), websocket_api.ERR_TIMEOUT, "Timeout"),
        (
            exceptions.HomeAssistantError("Failed to do X"),
            websocket_api.ERR_UNKNOWN_ERROR,
            "Failed to do X",
        ),
        (ValueError("Really bad"), websocket_api.ERR_UNKNOWN_ERROR, "Unknown error"),
    ):
        send_messages.clear()
        conn.async_handle_exception({"id": 5}, exc)
        assert len(send_messages) == 1
        assert send_messages[0]["error"]["code"] == code
        assert send_messages[0]["error"]["message"] == err
