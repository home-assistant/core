"""Test WebSocket Connection class."""
import asyncio
import logging
from unittest.mock import Mock

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components import websocket_api

from tests.common import MockUser


async def test_exception_handling():
    """Test handling of exceptions."""
    send_messages = []
    user = MockUser()
    refresh_token = Mock()
    conn = websocket_api.ActiveConnection(
        logging.getLogger(__name__), None, send_messages.append, user, refresh_token
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
        (
            exceptions.HomeAssistantError(),
            websocket_api.ERR_UNKNOWN_ERROR,
            "Unknown error",
        ),
    ):
        send_messages.clear()
        conn.async_handle_exception({"id": 5}, exc)
        assert len(send_messages) == 1
        assert send_messages[0]["error"]["code"] == code
        assert send_messages[0]["error"]["message"] == err
