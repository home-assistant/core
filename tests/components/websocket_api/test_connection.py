"""Test WebSocket Connection class."""

import asyncio
from contextlib import AbstractContextManager, nullcontext
import logging
from typing import Any
from unittest.mock import Mock, patch

from aiohttp.test_utils import make_mocked_request
import probatio
import pytest
from pytest_homeassistant.common import MockUser

from homeassistant import exceptions
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import REDACTED


@pytest.fixture
def revocable_connection(
    hass: HomeAssistant,
) -> tuple[websocket_api.ActiveConnection, Mock]:
    """Return an authenticated connection with an observable close callback."""
    hass.data[DOMAIN] = {}
    cancel_ws = Mock()
    connection = websocket_api.ActiveConnection(
        logging.getLogger(__name__),
        hass,
        Mock(),
        MockUser(),
        Mock(),
        remote=None,
        cancel_ws=cancel_ws,
    )
    return connection, cancel_ws


@pytest.mark.parametrize(
    ("exc", "code", "err", "log"),
    [
        (
            exceptions.Unauthorized(),
            websocket_api.ERR_UNAUTHORIZED,
            "Unauthorized",
            "Error handling message: Unauthorized (unauthorized)"
            " Mock User from 127.0.0.42 (Browser)",
        ),
        (
            probatio.Invalid("Invalid something"),
            websocket_api.ERR_INVALID_FORMAT,
            "Invalid something. Got {'id': 5}",
            "Error handling message: Invalid something."
            " Got {'id': 5} (invalid_format)"
            " Mock User from 127.0.0.42 (Browser)",
        ),
        (
            TimeoutError(),
            websocket_api.ERR_TIMEOUT,
            "Timeout",
            "Error handling message: Timeout (timeout)"
            " Mock User from 127.0.0.42 (Browser)",
        ),
        (
            exceptions.HomeAssistantError("Failed to do X"),
            websocket_api.ERR_HOME_ASSISTANT_ERROR,
            "Failed to do X",
            "Error handling message: Failed to do X"
            " (home_assistant_error)"
            " Mock User from 127.0.0.42 (Browser)",
        ),
        (
            exceptions.ServiceValidationError("Failed to do X"),
            websocket_api.ERR_HOME_ASSISTANT_ERROR,
            "Failed to do X",
            "Error handling message: Failed to do X"
            " (home_assistant_error)"
            " Mock User from 127.0.0.42 (Browser)",
        ),
        (
            ValueError("Really bad"),
            websocket_api.ERR_UNKNOWN_ERROR,
            "Unknown error",
            "Error handling message: Unknown error"
            " (unknown_error)"
            " Mock User from 127.0.0.42 (Browser)",
        ),
        (
            exceptions.HomeAssistantError,
            websocket_api.ERR_UNKNOWN_ERROR,
            "Unknown error",
            "Error handling message: Unknown error"
            " (unknown_error)"
            " Mock User from 127.0.0.42 (Browser)",
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


@pytest.mark.parametrize(
    ("command_error", "expected"),
    [
        pytest.param(None, nullcontext(), id="success"),
        pytest.param(ValueError, pytest.raises(ValueError), id="error"),
    ],
)
async def test_deferred_auth_close_blocks_further_commands(
    hass: HomeAssistant,
    revocable_connection: tuple[websocket_api.ActiveConnection, Mock],
    command_error: type[Exception] | None,
    expected: AbstractContextManager[object],
) -> None:
    """Test a revoked socket stops dispatching while its reply can still be sent."""
    connection, cancel_ws = revocable_connection
    handler = Mock()
    connection.handlers["test/command"] = (handler, False)
    binary_handler = Mock()
    handler_id, _ = connection.async_register_binary_handler(binary_handler)
    unsubscribe = Mock()
    connection.subscriptions[2] = unsubscribe
    connection.subscriptions["auth"] = unsubscribe_auth = Mock()
    command = Mock(side_effect=command_error)

    with (
        patch("homeassistant.components.websocket_api.connection.AUTH_CLOSE_DELAY", 0),
        expected,
        connection.async_defer_auth_close(),
    ):
        connection.async_auth_revoked()
        cancel_ws.assert_not_called()
        # Subscriptions end at once, so no updates reach the client. The revoke
        # callback being called stays until the connection closes.
        unsubscribe.assert_called_once_with()
        unsubscribe_auth.assert_not_called()
        connection.async_handle({"id": 1, "type": "test/command"})
        connection.async_handle_binary(handler_id, b"payload")
        handler.assert_not_called()
        binary_handler.assert_not_called()
        command()

    cancel_ws.assert_not_called()
    connection.send_result(1)
    await hass.async_block_till_done()

    cancel_ws.assert_called_once_with()


async def test_auth_close_from_another_task_is_not_deferred(
    revocable_connection: tuple[websocket_api.ActiveConnection, Mock],
) -> None:
    """Test an opted-in command cannot delay somebody else's revocation."""
    connection, cancel_ws = revocable_connection

    async def revoke() -> None:
        connection.async_auth_revoked()

    with connection.async_defer_auth_close():
        await asyncio.create_task(revoke())
        cancel_ws.assert_called_once_with()

    cancel_ws.assert_called_once_with()


async def test_deferred_auth_close_runs_during_shutdown(
    hass: HomeAssistant,
    revocable_connection: tuple[websocket_api.ActiveConnection, Mock],
) -> None:
    """Test shutdown closes a revoked socket without waiting for its grace period."""
    connection, cancel_ws = revocable_connection

    with patch(
        "homeassistant.components.websocket_api.connection.AUTH_CLOSE_DELAY", 3600
    ):
        with connection.async_defer_auth_close():
            connection.async_auth_revoked()
        cancel_ws.assert_not_called()

        await hass.async_stop(force=True)

    cancel_ws.assert_called_once_with()


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
    connection.async_handle_exception(msg, probatio.Invalid("bad input"))

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
