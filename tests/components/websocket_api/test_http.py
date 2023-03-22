"""Test Websocket API http module."""
import asyncio
from datetime import timedelta
from typing import Any
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
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed
from tests.typing import WebSocketGenerator


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
    hass: HomeAssistant, mock_low_queue, websocket_client
) -> None:
    """Test get_panels command."""
    for idx in range(10):
        await websocket_client.send_json({"id": idx + 1, "type": "ping"})
    msg = await websocket_client.receive()
    assert msg.type == WSMsgType.close


async def test_pending_msg_peak(
    hass: HomeAssistant,
    mock_low_peak,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test pending msg overflow command."""
    orig_handler = http.WebSocketHandler
    instance = None

    def instantiate_handler(*args):
        nonlocal instance
        instance = orig_handler(*args)
        return instance

    with patch(
        "homeassistant.components.websocket_api.http.WebSocketHandler",
        instantiate_handler,
    ):
        websocket_client = await hass_ws_client()

    # Kill writer task and fill queue past peak
    for _ in range(5):
        instance._to_write.put_nowait(None)

    # Trigger the peak check
    instance._send_message({})

    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=const.PENDING_MSG_PEAK_TIME + 1)
    )

    msg = await websocket_client.receive()
    assert msg.type == WSMsgType.close

    assert "Client unable to keep up with pending messages" in caplog.text


async def test_pending_msg_peak_but_does_not_overflow(
    hass: HomeAssistant,
    mock_low_peak,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test pending msg hits the low peak but recovers and does not overflow."""
    orig_handler = http.WebSocketHandler
    instance: http.WebSocketHandler | None = None

    def instantiate_handler(*args):
        nonlocal instance
        instance = orig_handler(*args)
        return instance

    with patch(
        "homeassistant.components.websocket_api.http.WebSocketHandler",
        instantiate_handler,
    ):
        websocket_client = await hass_ws_client()

    assert instance is not None

    # Kill writer task and fill queue past peak
    for _ in range(5):
        instance._to_write.put_nowait(None)

    # Trigger the peak check
    instance._send_message({})

    # Clear the queue
    while instance._to_write.qsize() > 0:
        instance._to_write.get_nowait()

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
    assert (
        f"Unable to serialize to JSON. Bad data found at $.result[0](State: test_domain.entity).attributes.bad={bad_data}(<class 'object'>"
        in caplog.text
    )


async def test_prepare_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failing to prepare."""
    with patch(
        "homeassistant.components.websocket_api.http.web.WebSocketResponse.prepare",
        side_effect=(asyncio.TimeoutError, web.WebSocketResponse.prepare),
    ), pytest.raises(ServerDisconnectedError):
        await hass_ws_client(hass)

    assert "Timeout preparing request" in caplog.text


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
