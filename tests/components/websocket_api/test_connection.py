"""Test WebSocket Connection class."""

import logging
from typing import Any
from unittest.mock import Mock, patch

from aiohttp.test_utils import make_mocked_request
import pytest
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import REDACTED

from tests.common import MockUser


@pytest.mark.parametrize(
    ("exc", "code", "err", "log"),
    [
        (
            exceptions.Unauthorized(),
            websocket_api.ERR_UNAUTHORIZED,
            "Unauthorized",
            "Error handling message: Unauthorized (unauthorized) Mock User from 127.0.0.42 (Browser)",
        ),
        (
            vol.Invalid("Invalid something"),
            websocket_api.ERR_INVALID_FORMAT,
            "Invalid something. Got {'id': 5}",
            "Error handling message: Invalid something. Got {'id': 5} (invalid_format) Mock User from 127.0.0.42 (Browser)",
        ),
        (
            TimeoutError(),
            websocket_api.ERR_TIMEOUT,
            "Timeout",
            "Error handling message: Timeout (timeout) Mock User from 127.0.0.42 (Browser)",
        ),
        (
            exceptions.HomeAssistantError("Failed to do X"),
            websocket_api.ERR_HOME_ASSISTANT_ERROR,
            "Failed to do X",
            "Error handling message: Failed to do X (home_assistant_error) Mock User from 127.0.0.42 (Browser)",
        ),
        (
            exceptions.ServiceValidationError("Failed to do X"),
            websocket_api.ERR_HOME_ASSISTANT_ERROR,
            "Failed to do X",
            "Error handling message: Failed to do X (home_assistant_error) Mock User from 127.0.0.42 (Browser)",
        ),
        (
            ValueError("Really bad"),
            websocket_api.ERR_UNKNOWN_ERROR,
            "Unknown error",
            "Error handling message: Unknown error (unknown_error) Mock User from 127.0.0.42 (Browser)",
        ),
        (
            exceptions.HomeAssistantError,
            websocket_api.ERR_UNKNOWN_ERROR,
            "Unknown error",
            "Error handling message: Unknown error (unknown_error) Mock User from 127.0.0.42 (Browser)",
        ),
    ],
)
async def test_exception_handling(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
    code: str,
    err: str,
    log: str,
) -> None:
    """Test handling of exceptions."""
    send_messages = []
    user = MockUser()
    refresh_token = Mock()
    hass.data[DOMAIN] = {}

    def get_extra_info(key: str) -> Any | None:
        if key == "sslcontext":
            return True

        if key == "peername":
            return ("127.0.0.42", 8123)

        return None

    mocked_transport = Mock()
    mocked_transport.get_extra_info = get_extra_info
    mocked_request = make_mocked_request(
        "GET",
        "/api/websocket",
        headers={"Host": "example.com", "User-Agent": "Browser"},
        transport=mocked_transport,
    )

    with patch(
        "homeassistant.components.websocket_api.connection.current_request",
    ) as current_request:
        current_request.get.return_value = mocked_request
        conn = websocket_api.ActiveConnection(
            logging.getLogger(__name__),
            hass,
            send_messages.append,
            user,
            refresh_token,
            remote="127.0.0.42",
        )

        conn.async_handle_exception({"id": 5}, exc)
    assert len(send_messages) == 1
    assert send_messages[0]["error"]["code"] == code
    assert send_messages[0]["error"]["message"] == err
    assert log in caplog.text


async def test_binary_handler_registration() -> None:
    """Test binary handler registration."""
    connection = websocket_api.ActiveConnection(
        None, Mock(data={websocket_api.DOMAIN: None}), None, None, Mock(), remote=None
    )

    # One filler to align indexes with prefix numbers
    unsubs = [None]
    fake_handler = object()
    for i in range(255):
        prefix, unsub = connection.async_register_binary_handler(fake_handler)
        assert prefix == i + 1
        unsubs.append(unsub)

    with pytest.raises(RuntimeError):
        connection.async_register_binary_handler(None)

    unsubs[15]()

    # Verify we reuse an unsubscribed prefix
    prefix, unsub = connection.async_register_binary_handler(None)
    assert prefix == 15


async def test_credential_redaction(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test credential redaction."""
    send_messages = []
    user = MockUser()
    refresh_token = Mock()
    hass.data[DOMAIN] = {}
    test_input = ["valid detail information", "secretpassword", "api-token-12345"]

    connection = websocket_api.ActiveConnection(
        logging.getLogger(__name__),
        hass,
        send_messages.append,
        user,
        refresh_token,
        remote=None,
    )

    msg = {
        "id": 5,
        "detail": test_input[0],
        "password": test_input[1],
        "token": test_input[2],
    }
    connection.async_handle_exception(msg, vol.Invalid("bad input"))

    assert len(send_messages) == 1
    error_message = send_messages[0]["error"]["message"]
    assert test_input[0] in error_message
    assert test_input[1] not in error_message
    assert test_input[2] not in error_message
    assert REDACTED in error_message

    msg = {"type": "auth", "access_token": test_input[2]}
    connection.async_handle(msg)

    assert len(send_messages) == 2
    assert send_messages[1]["error"]["message"] == "Message incorrectly formatted."
    assert test_input[2] not in caplog.text
    assert REDACTED in caplog.text
