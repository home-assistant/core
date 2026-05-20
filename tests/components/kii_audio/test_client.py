"""Tests for the Kii Audio WebSocket client."""

import asyncio
from typing import Any

import pytest

from homeassistant.components.kii_audio.client import (
    KiiAudioClient,
    KiiAudioClientError,
)


def test_handle_message_with_data_payload() -> None:
    """Test handling a WebSocket event with a data payload."""
    client = KiiAudioClient(None, "192.0.2.1")  # type: ignore[arg-type]
    events: list[tuple[str, dict[str, Any]]] = []
    client.add_listener(lambda event, payload: events.append((event, payload)))

    client._handle_message(
        '{"event":"pushZoneSetting","data":{"zoneId":"zone-id","value":1}}'
    )

    assert events == [("pushZoneSetting", {"zoneId": "zone-id", "value": 1})]


def test_handle_message_with_flat_payload() -> None:
    """Test handling a WebSocket event with a flat payload."""
    client = KiiAudioClient(None, "192.0.2.1")  # type: ignore[arg-type]
    events: list[tuple[str, dict[str, Any]]] = []
    client.add_listener(lambda event, payload: events.append((event, payload)))

    client._handle_message('{"event":"pushSystemInfo","systemName":"Kii"}')

    assert events == [("pushSystemInfo", {"systemName": "Kii"})]


def test_handle_message_ignores_invalid_messages() -> None:
    """Test invalid WebSocket messages are ignored."""
    client = KiiAudioClient(None, "192.0.2.1")  # type: ignore[arg-type]
    events: list[tuple[str, dict[str, Any]]] = []
    client.add_listener(lambda event, payload: events.append((event, payload)))

    client._handle_message("not json")
    client._handle_message("[]")
    client._handle_message('{"data":{}}')

    assert events == []


class FakeWebSocket:
    """Fake WebSocket for client command tests."""

    def __init__(self) -> None:
        """Initialize the fake WebSocket."""
        self.closed = False
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        """Record a JSON payload."""
        self.sent.append(payload)

    async def close(self) -> None:
        """Close the fake WebSocket."""
        self.closed = True


async def test_send_event_requires_active_websocket() -> None:
    """Test commands fail when the connected websocket is gone."""
    client = KiiAudioClient(None, "192.0.2.1")  # type: ignore[arg-type]
    client._connected.set()

    with pytest.raises(KiiAudioClientError, match="WebSocket is not connected"):
        await client.send_event("getSystemInfo")


async def test_set_zone_setting_sends_expected_payload() -> None:
    """Test zone setting commands are sent through the WebSocket."""
    client = KiiAudioClient(None, "192.0.2.1")  # type: ignore[arg-type]
    ws = FakeWebSocket()
    client._ws = ws  # type: ignore[assignment]
    client._connected.set()

    await client.set_zone_setting("zone-id", "audio.mute", True)

    assert ws.sent == [
        {
            "event": "setZoneSetting",
            "data": {"zoneId": "zone-id", "setting": "audio.mute", "value": True},
        }
    ]


async def test_stop_closes_websocket_and_cancels_listener_task() -> None:
    """Test stopping the client cleans up active WebSocket state."""
    client = KiiAudioClient(None, "192.0.2.1")  # type: ignore[arg-type]
    ws = FakeWebSocket()
    client._ws = ws  # type: ignore[assignment]
    client._connected.set()
    client._listen_task = asyncio.create_task(asyncio.sleep(3600))

    await client.stop()

    assert ws.closed is True
    assert client._ws is None
    assert client._listen_task is None
    assert not client._connected.is_set()


def test_connection_state_listeners_are_notified() -> None:
    """Test connection state listeners receive changes."""
    client = KiiAudioClient(None, "192.0.2.1")  # type: ignore[arg-type]
    states: list[bool] = []
    client.add_connection_listener(states.append)

    client._notify_connection_state(True)
    client._notify_connection_state(False)

    assert states == [True, False]
