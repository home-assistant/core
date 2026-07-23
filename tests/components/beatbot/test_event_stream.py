"""Tests for the Beatbot cloud WebSocket event contract."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.beatbot.iot.event_stream import (
    BeatbotEventClient,
    _RefreshToken,
)
from homeassistant.core import HomeAssistant


def _client(hass: HomeAssistant) -> tuple[BeatbotEventClient, Mock]:
    coordinator = Mock()
    client = BeatbotEventClient(
        hass,
        SimpleNamespace(entry_id="entry"),
        SimpleNamespace(),
        SimpleNamespace(event_stream_url="ws://example/events"),
        coordinator,
    )
    return client, coordinator


def _event(
    event_id: str,
    event_type: str,
    payload: dict | None,
    device_id: str = "dev-1",
) -> str:
    return json.dumps(
        {
            "eventId": event_id,
            "type": event_type,
            "deviceId": device_id,
            "occurredAt": "2026-07-01T08:00:00Z",
            "payload": payload,
        }
    )


def test_start_registers_entry_background_task(hass: HomeAssistant) -> None:
    """The lifetime WebSocket supervisor must not block HA startup."""
    task = Mock()
    entry = SimpleNamespace(
        entry_id="entry",
        async_create_background_task=Mock(return_value=task),
    )
    client = BeatbotEventClient(
        hass,
        entry,
        SimpleNamespace(),
        SimpleNamespace(event_stream_url="ws://example/events"),
        Mock(),
    )

    try:
        client.async_start()
        call_args = entry.async_create_background_task.call_args.args
    finally:
        entry.async_create_background_task.call_args.args[1].close()

    entry.async_create_background_task.assert_called_once()
    assert call_args[0] is hass
    assert call_args[1].cr_code is BeatbotEventClient._run.__code__
    assert call_args[2] == "beatbot_event_stream_entry"
    assert client._task is task


def test_property_event_routes_incremental_state(hass: HomeAssistant) -> None:
    """Route a property event to the coordinator."""
    client, coordinator = _client(hass)

    client._handle_text_message(
        _event(
            "event-1",
            "properties_changed",
            {"interfaceInfo": "vacuum.battery", "value": 76},
        )
    )

    coordinator.async_apply_device_event.assert_called_once_with(
        "dev-1", {"vacuum.battery": 76}
    )


def test_status_event_routes_online_state(hass: HomeAssistant) -> None:
    """Route a status event to the coordinator."""
    client, coordinator = _client(hass)

    client._handle_text_message(_event("event-2", "status", {"online": False}))

    coordinator.async_apply_device_event.assert_called_once_with(
        "dev-1", None, is_online=False
    )


def test_duplicate_event_is_applied_once(hass: HomeAssistant) -> None:
    """Apply duplicate event identifiers only once."""
    client, coordinator = _client(hass)
    message = _event(
        "event-3",
        "properties_changed",
        {"interfaceInfo": "sensor.error", "value": 4},
    )

    client._handle_text_message(message)
    client._handle_text_message(message)

    coordinator.async_apply_device_event.assert_called_once()


def test_malformed_and_unknown_events_do_not_route(hass: HomeAssistant) -> None:
    """Ignore malformed and unsupported events."""
    client, coordinator = _client(hass)

    client._handle_text_message("not-json")
    client._handle_text_message(_event("event-4", "status", {"online": "yes"}))
    client._handle_text_message(_event("event-5", "future_type", {}))

    coordinator.async_apply_device_event.assert_not_called()


async def test_device_added_reloads_entry(hass: HomeAssistant) -> None:
    """Reload the entry after a device-added event."""
    client, coordinator = _client(hass)
    hass.config_entries.async_reload = AsyncMock(return_value=True)

    client._handle_text_message(
        _event(
            "event-added",
            "device_added",
            {
                "deviceId": "dev-1",
                "productId": "product-1",
                "productCategory": "pool_clean_bot",
            },
        )
    )
    await hass.async_block_till_done()

    hass.config_entries.async_reload.assert_awaited_once_with("entry")
    coordinator.async_apply_device_event.assert_not_called()


async def test_device_removed_with_null_payload_reloads_entry(
    hass: HomeAssistant,
) -> None:
    """Reload the entry after a device-removed event."""
    client, coordinator = _client(hass)
    hass.config_entries.async_reload = AsyncMock(return_value=True)

    client._handle_text_message(_event("event-removed", "device_removed", None))
    await hass.async_block_till_done()

    hass.config_entries.async_reload.assert_awaited_once_with("entry")
    coordinator.async_apply_device_event.assert_not_called()


async def test_malformed_device_lifecycle_events_do_not_reload(
    hass: HomeAssistant,
) -> None:
    """Ignore malformed device lifecycle events."""
    client, _ = _client(hass)
    hass.config_entries.async_reload = AsyncMock(return_value=True)

    client._handle_text_message(
        _event("bad-added", "device_added", {"deviceId": "another-device"})
    )
    client._handle_text_message(_event("bad-removed", "device_removed", {}))
    await hass.async_block_till_done()

    hass.config_entries.async_reload.assert_not_awaited()


async def test_stop_is_idempotent(hass: HomeAssistant) -> None:
    """Allow the event client to be stopped repeatedly."""
    client, _ = _client(hass)

    await client.async_stop()
    await client.async_stop()


async def test_rejected_token_is_refreshed_only_once(hass: HomeAssistant) -> None:
    """Refresh a rejected access token only once."""
    entry = SimpleNamespace(
        entry_id="entry",
        data={"token": {"access_token": "old", "refresh_token": "refresh"}},
    )
    implementation = SimpleNamespace(
        async_refresh_token=AsyncMock(
            return_value={"access_token": "new", "refresh_token": "refresh"}
        )
    )
    oauth_session = SimpleNamespace(token=entry.data["token"])

    async def _ensure_token_valid() -> None:
        new_token = await implementation.async_refresh_token(oauth_session.token)
        entry.data = {"token": new_token}
        oauth_session.token = new_token

    oauth_session.async_ensure_token_valid = AsyncMock(side_effect=_ensure_token_valid)
    client = BeatbotEventClient(
        hass,
        entry,
        oauth_session,
        SimpleNamespace(event_stream_url="ws://example/events"),
        Mock(),
    )
    hass.config_entries.async_update_entry = Mock(
        side_effect=lambda config_entry, data: setattr(config_entry, "data", data)
    )

    await client._async_refresh_token_once("old")
    oauth_session.token = entry.data["token"]
    await client._async_refresh_token_once("old")

    implementation.async_refresh_token.assert_awaited_once()


async def test_repeated_handshake_401_starts_reauth(hass: HomeAssistant) -> None:
    """Start reauthentication after a repeated handshake rejection."""
    client, _ = _client(hass)
    client._handshake_refresh_attempted = True
    client._connect_and_receive = AsyncMock(
        side_effect=_RefreshToken("rejected-again", handshake=True)
    )
    client._entry.async_start_reauth = Mock()

    await client._run()

    client._entry.async_start_reauth.assert_called_once_with(hass)


async def test_reconnect_requests_full_refresh(hass: HomeAssistant) -> None:
    """Request a full refresh after reconnecting the event stream."""
    client, coordinator = _client(hass)
    coordinator.async_request_refresh = AsyncMock()
    client._has_connected = True

    class _WebSocket:
        closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            self.closed = True

        async def receive(self, *, timeout):
            raise asyncio.CancelledError

        async def close(self):
            self.closed = True

    client._oauth_session.async_ensure_token_valid = AsyncMock()
    client._oauth_session.token = {"access_token": "token"}
    websocket = _WebSocket()
    session = SimpleNamespace(ws_connect=AsyncMock(return_value=websocket))

    with (
        patch(
            "homeassistant.components.beatbot.iot.event_stream.async_get_clientsession",
            return_value=session,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await client._connect_and_receive()

    coordinator.async_request_refresh.assert_awaited_once()
