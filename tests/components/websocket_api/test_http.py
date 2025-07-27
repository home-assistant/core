"""Test Websocket API http module."""

import asyncio
from datetime import timedelta
from typing import Any, cast
from unittest.mock import patch

from aiohttp import ServerDisconnectedError, WSMsgType, web
import pytest

from homeassistant.components.websocket_api import (
    async_register_command,
    const,
    http,
    websocket_command,
)
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_call_logger_set_level, async_fire_time_changed
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture
def mock_low_queue():
    """Mock a low queue."""
    with patch("homeassistant.components.websocket_api.http.MAX_PENDING_MSG", 1):
        yield


@pytest.fixture
def mock_low_peak():
    """Mock a low queue."""
    with patch("homeassistant.components.websocket_api.http.PENDING_MSG_PEAK", 5):
        yield


async def test_pending_msg_overflow(
    hass: HomeAssistant, mock_low_queue, websocket_client: MockHAClientWebSocket
) -> None:
    """Test pending messages overflows."""
    for idx in range(10):
        await websocket_client.send_json({"id": idx + 1, "type": "ping"})
    msg = await websocket_client.receive()
    assert msg.type is WSMsgType.CLOSE


async def test_cleanup_on_cancellation(
    hass: HomeAssistant, websocket_client: MockHAClientWebSocket
) -> None:
    """Test cleanup on cancellation."""

    subscriptions = None

    # Register a handler that registers a subscription
    @callback
    @websocket_command(
        {
            "type": "fake_subscription",
        }
    )
    def fake_subscription(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        nonlocal subscriptions
        msg_id: int = msg["id"]
        connection.subscriptions[msg_id] = callback(lambda: None)
        connection.send_result(msg_id)
        subscriptions = connection.subscriptions

    async_register_command(hass, fake_subscription)

    # Register a handler that raises on cancel
    @callback
    @websocket_command(
        {
            "type": "subscription_that_raises_on_cancel",
        }
    )
    def subscription_that_raises_on_cancel(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        nonlocal subscriptions
        msg_id: int = msg["id"]

        @callback
        def _raise():
            raise ValueError

        connection.subscriptions[msg_id] = _raise
        connection.send_result(msg_id)
        subscriptions = connection.subscriptions

    async_register_command(hass, subscription_that_raises_on_cancel)

    # Register a handler that cancels in handler
    @callback
    @websocket_command(
        {
            "type": "cancel_in_handler",
        }
    )
    def cancel_in_handler(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        raise asyncio.CancelledError

    async_register_command(hass, cancel_in_handler)

    await websocket_client.send_json({"id": 1, "type": "ping"})
    msg = await websocket_client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == "pong"
    assert not subscriptions
    await websocket_client.send_json({"id": 2, "type": "fake_subscription"})
    msg = await websocket_client.receive_json()
    assert msg["id"] == 2
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    assert len(subscriptions) == 2
    await websocket_client.send_json(
        {"id": 3, "type": "subscription_that_raises_on_cancel"}
    )
    msg = await websocket_client.receive_json()
    assert msg["id"] == 3
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    assert len(subscriptions) == 3
    await websocket_client.send_json({"id": 4, "type": "cancel_in_handler"})
    await hass.async_block_till_done()
    msg = await websocket_client.receive()
    assert msg.type == WSMsgType.close
    assert len(subscriptions) == 0


async def test_delayed_response_handler(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a handler that responds after a connection has already been closed."""

    subscriptions = None

    # Register a handler that responds after it returns
    @callback
    @websocket_command(
        {
            "type": "late_responder",
        }
    )
    def async_late_responder(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        msg_id: int = msg["id"]
        nonlocal subscriptions
        subscriptions = connection.subscriptions
        connection.subscriptions[msg_id] = lambda: None
        connection.send_result(msg_id)

        async def _async_late_send_message():
            await asyncio.sleep(0.05)
            connection.send_event(msg_id, {"event": "any"})

        hass.async_create_task(_async_late_send_message())

    async_register_command(hass, async_late_responder)

    await websocket_client.send_json({"id": 1, "type": "ping"})
    msg = await websocket_client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == "pong"
    assert not subscriptions
    await websocket_client.send_json({"id": 2, "type": "late_responder"})
    msg = await websocket_client.receive_json()
    assert msg["id"] == 2
    assert msg["type"] == "result"
    assert len(subscriptions) == 2
    assert await websocket_client.close()
    await hass.async_block_till_done()
    assert len(subscriptions) == 0

    assert "Tried to send message" in caplog.text
    assert "on closed connection" in caplog.text


async def test_ensure_disconnect_invalid_json(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we get disconnected when sending invalid JSON."""

    await websocket_client.send_json({"id": 1, "type": "ping"})
    msg = await websocket_client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == "pong"
    await websocket_client.send_str("[--INVALID-JSON--]")
    msg = await websocket_client.receive()
    assert msg.type == WSMsgType.CLOSE


async def test_ensure_disconnect_invalid_binary(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we get disconnected when sending invalid bytes."""

    await websocket_client.send_json({"id": 1, "type": "ping"})
    msg = await websocket_client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == "pong"
    await websocket_client.send_bytes(b"")
    msg = await websocket_client.receive()
    assert msg.type == WSMsgType.CLOSE


async def test_pending_msg_peak(
    hass: HomeAssistant,
    mock_low_peak,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test pending msg overflow command."""
    orig_handler = http.WebSocketHandler
    setup_instance: http.WebSocketHandler | None = None

    def instantiate_handler(*args):
        nonlocal setup_instance
        setup_instance = orig_handler(*args)
        return setup_instance

    with patch(
        "homeassistant.components.websocket_api.http.WebSocketHandler",
        instantiate_handler,
    ):
        websocket_client = await hass_ws_client()

    instance: http.WebSocketHandler = cast(http.WebSocketHandler, setup_instance)

    # Fill the queue past the allowed peak
    for _ in range(20):
        instance._send_message({"overload": "message"})

    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=const.PENDING_MSG_PEAK_TIME + 1)
    )

    msg = await websocket_client.receive()
    assert msg.type is WSMsgType.CLOSE
    assert "Client unable to keep up with pending messages" in caplog.text
    assert "Stayed over 5 for 10 seconds" in caplog.text
    assert "overload" in caplog.text


async def test_pending_msg_peak_recovery(
    hass: HomeAssistant,
    mock_low_peak,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test pending msg nears the peak but recovers."""
    orig_handler = http.WebSocketHandler
    setup_instance: http.WebSocketHandler | None = None

    def instantiate_handler(*args):
        nonlocal setup_instance
        setup_instance = orig_handler(*args)
        return setup_instance

    with patch(
        "homeassistant.components.websocket_api.http.WebSocketHandler",
        instantiate_handler,
    ):
        websocket_client = await hass_ws_client()

    instance: http.WebSocketHandler = cast(http.WebSocketHandler, setup_instance)

    # Make sure the call later is started
    for _ in range(10):
        instance._send_message({})

    for _ in range(10):
        msg = await websocket_client.receive()
        assert msg.type == WSMsgType.TEXT

    instance._send_message({})
    msg = await websocket_client.receive()
    assert msg.type == WSMsgType.TEXT

    # Cleanly shutdown
    instance._send_message({})
    instance._handle_task.cancel()

    msg = await websocket_client.receive()
    assert msg.type is WSMsgType.CLOSE
    assert "Client unable to keep up with pending messages" not in caplog.text


async def test_pending_msg_peak_but_does_not_overflow(
    hass: HomeAssistant,
    mock_low_peak,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test pending msg hits the low peak but recovers and does not overflow."""
    orig_handler = http.WebSocketHandler
    setup_instance: http.WebSocketHandler | None = None

    def instantiate_handler(*args):
        nonlocal setup_instance
        setup_instance = orig_handler(*args)
        return setup_instance

    with patch(
        "homeassistant.components.websocket_api.http.WebSocketHandler",
        instantiate_handler,
    ):
        websocket_client = await hass_ws_client()

    instance: http.WebSocketHandler = cast(http.WebSocketHandler, setup_instance)

    # Kill writer task and fill queue past peak
    for _ in range(5):
        instance._message_queue.append(None)

    # Trigger the peak check
    instance._send_message({})

    # Clear the queue
    instance._message_queue.clear()

    # Trigger the peak clear
    instance._send_message({})

    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=const.PENDING_MSG_PEAK_TIME + 1)
    )

    msg = await websocket_client.receive()
    assert msg.type == WSMsgType.TEXT

    assert "Client unable to keep up with pending messages" not in caplog.text


async def test_non_json_message(
    hass: HomeAssistant, websocket_client, caplog: pytest.LogCaptureFixture
) -> None:
    """Test trying to serialize non JSON objects."""
    bad_data = object()
    hass.states.async_set("test_domain.entity", "testing", {"bad": bad_data})
    await websocket_client.send_json({"id": 5, "type": "get_states"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == []
    assert "Unable to serialize to JSON. Bad data found" in caplog.text
    assert "State: test_domain.entity" in caplog.text
    assert "bad=<object" in caplog.text


async def test_prepare_fail_timeout(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failing to prepare due to timeout."""
    with (
        patch(
            "homeassistant.components.websocket_api.http.web.WebSocketResponse.prepare",
            side_effect=(TimeoutError, web.WebSocketResponse.prepare),
        ),
        pytest.raises(ServerDisconnectedError),
    ):
        await hass_ws_client(hass)

    assert "Timeout preparing request" in caplog.text


async def test_prepare_fail_connection_reset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failing to prepare due to connection reset."""
    with (
        patch(
            "homeassistant.components.websocket_api.http.web.WebSocketResponse.prepare",
            side_effect=(ConnectionResetError, web.WebSocketResponse.prepare),
        ),
        pytest.raises(ServerDisconnectedError),
    ):
        await hass_ws_client(hass)

    assert "Connection reset by peer while preparing WebSocket" in caplog.text


async def test_enable_coalesce(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test enabling coalesce."""
    websocket_client = await hass_ws_client(hass)

    await websocket_client.send_json(
        {
            "id": 1,
            "type": "supported_features",
            "features": {const.FEATURE_COALESCE_MESSAGES: 1},
        }
    )
    msg = await websocket_client.receive_json()
    assert msg["id"] == 1
    assert msg["success"] is True
    send_tasks: list[asyncio.Future] = []
    ids: set[int] = set()
    start_id = 2

    for idx in range(10):
        id_ = idx + start_id
        ids.add(id_)
        send_tasks.append(websocket_client.send_json({"id": id_, "type": "ping"}))

    await asyncio.gather(*send_tasks)
    returned_ids: set[int] = set()
    for _ in range(10):
        msg = await websocket_client.receive_json()
        assert msg["type"] == "pong"
        returned_ids.add(msg["id"])

    assert ids == returned_ids

    # Now close
    send_tasks_with_close: list[asyncio.Future] = []
    start_id = 12
    for idx in range(10):
        id_ = idx + start_id
        send_tasks_with_close.append(
            websocket_client.send_json({"id": id_, "type": "ping"})
        )

    send_tasks_with_close.append(websocket_client.close())
    send_tasks_with_close.append(websocket_client.send_json({"id": 50, "type": "ping"}))

    with pytest.raises(ConnectionResetError):
        await asyncio.gather(*send_tasks_with_close)


async def test_binary_message(
    hass: HomeAssistant, websocket_client, caplog: pytest.LogCaptureFixture
) -> None:
    """Test binary messages."""
    binary_payloads = {
        104: ([], asyncio.Future()),
        105: ([], asyncio.Future()),
    }

    # Register a handler
    @callback
    @websocket_command(
        {
            "type": "get_binary_message_handler",
        }
    )
    def get_binary_message_handler(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ):
        unsub = None

        @callback
        def binary_message_handler(
            hass: HomeAssistant, connection: ActiveConnection, payload: bytes
        ):
            nonlocal unsub
            if msg["id"] == 103:
                raise ValueError("Boom")

            if payload:
                binary_payloads[msg["id"]][0].append(payload)
            else:
                binary_payloads[msg["id"]][1].set_result(
                    b"".join(binary_payloads[msg["id"]][0])
                )
                unsub()

        prefix, unsub = connection.async_register_binary_handler(binary_message_handler)

        connection.send_result(msg["id"], {"prefix": prefix})

    async_register_command(hass, get_binary_message_handler)

    # Register multiple binary handlers
    for i in range(101, 106):
        await websocket_client.send_json(
            {"id": i, "type": "get_binary_message_handler"}
        )
        result = await websocket_client.receive_json()
        assert result["id"] == i
        assert result["type"] == const.TYPE_RESULT
        assert result["success"]
        assert result["result"]["prefix"] == i - 100

    # Send message to binary
    await websocket_client.send_bytes((0).to_bytes(1, "big") + b"test0")
    await websocket_client.send_bytes((3).to_bytes(1, "big") + b"test3")
    await websocket_client.send_bytes((3).to_bytes(1, "big") + b"test3")
    await websocket_client.send_bytes((10).to_bytes(1, "big") + b"test10")
    await websocket_client.send_bytes((4).to_bytes(1, "big") + b"test4")
    await websocket_client.send_bytes((4).to_bytes(1, "big") + b"")
    await websocket_client.send_bytes((5).to_bytes(1, "big") + b"test5")
    await websocket_client.send_bytes((5).to_bytes(1, "big") + b"test5-2")
    await websocket_client.send_bytes((5).to_bytes(1, "big") + b"")

    # Verify received
    assert await binary_payloads[104][1] == b"test4"
    assert await binary_payloads[105][1] == b"test5test5-2"
    assert "Error handling binary message" in caplog.text
    assert "Received binary message for non-existing handler 0" in caplog.text
    assert "Received binary message for non-existing handler 3" in caplog.text
    assert "Received binary message for non-existing handler 10" in caplog.text


async def test_enable_disable_debug_logging(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test enabling and disabling debug logging."""
    assert await async_setup_component(hass, "logger", {"logger": {}})
    async with async_call_logger_set_level(
        "homeassistant.components.websocket_api", "DEBUG", hass=hass, caplog=caplog
    ):
        await websocket_client.send_json({"id": 1, "type": "ping"})
        msg = await websocket_client.receive_json()
        assert msg["id"] == 1
        assert msg["type"] == "pong"
        assert 'Sending b\'{"id":1,"type":"pong"}\'' in caplog.text
    async with async_call_logger_set_level(
        "homeassistant.components.websocket_api", "WARNING", hass=hass, caplog=caplog
    ):
        await websocket_client.send_json({"id": 2, "type": "ping"})
        msg = await websocket_client.receive_json()
        assert msg["id"] == 2
        assert msg["type"] == "pong"
        assert 'Sending b\'{"id":2,"type":"pong"}\'' not in caplog.text
