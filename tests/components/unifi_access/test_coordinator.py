"""Tests for the UniFi Access coordinator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

import pytest
from unifi_access_api.models.websocket import (
    LocationUpdateData,
    LocationUpdateState,
    LocationUpdateV2,
    V2LocationState,
    V2LocationUpdate,
    V2LocationUpdateData,
    WebsocketMessage,
)

from homeassistant.components.lock import LockState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _get_ws_handlers(
    mock_client: MagicMock,
) -> dict[str, Callable[[WebsocketMessage], Awaitable[None]]]:
    """Extract WebSocket message handlers from mock client."""
    return mock_client.start_websocket.call_args[0][0]


def _get_on_connect(mock_client: MagicMock) -> Callable[[], None]:
    """Extract on_connect callback from mock client."""
    return mock_client.start_websocket.call_args[1]["on_connect"]


def _get_on_disconnect(mock_client: MagicMock) -> Callable[[], None]:
    """Extract on_disconnect callback from mock client."""
    return mock_client.start_websocket.call_args[1]["on_disconnect"]


def _make_ws_message(
    event: str, door_id: str, lock: str
) -> LocationUpdateV2 | V2LocationUpdate:
    """Build a WebSocket message for the given event type."""
    if event == "access.data.device.location_update_v2":
        return LocationUpdateV2(
            event=event,
            data=LocationUpdateData(
                id=door_id,
                location_type="door",
                state=LocationUpdateState(lock=lock),
            ),
        )
    return V2LocationUpdate(
        event=event,
        data=V2LocationUpdateData(
            id=door_id,
            state=V2LocationState(lock=lock),
        ),
    )


async def test_ws_disconnect_marks_entities_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket disconnect marks entities as unavailable."""
    assert hass.states.get("lock.front_door").state == LockState.LOCKED

    on_disconnect = _get_on_disconnect(mock_client)
    on_disconnect()
    await hass.async_block_till_done()

    assert hass.states.get("lock.front_door").state == "unavailable"
    assert hass.states.get("lock.back_door").state == "unavailable"


async def test_ws_reconnect_restores_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket reconnect restores entity availability."""
    on_disconnect = _get_on_disconnect(mock_client)
    on_connect = _get_on_connect(mock_client)

    on_disconnect()
    await hass.async_block_till_done()
    assert hass.states.get("lock.front_door").state == "unavailable"

    on_connect()
    await hass.async_block_till_done()

    assert hass.states.get("lock.front_door").state == LockState.LOCKED
    assert hass.states.get("lock.back_door").state == LockState.UNLOCKED


async def test_ws_connect_no_refresh_when_healthy(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket connect does not trigger redundant refresh when healthy."""
    on_connect = _get_on_connect(mock_client)

    on_connect()
    await hass.async_block_till_done()

    assert mock_client.get_doors.call_count == 1


@pytest.mark.parametrize(
    "event",
    [
        "access.data.device.location_update_v2",
        "access.data.v2.location.update",
    ],
)
@pytest.mark.parametrize(
    ("door_id", "entity_id", "lock_value", "expected_state"),
    [
        ("door-001", "lock.front_door", "unlocked", LockState.UNLOCKED),
        ("door-002", "lock.back_door", "locked", LockState.LOCKED),
    ],
)
async def test_ws_update_changes_lock_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    event: str,
    door_id: str,
    entity_id: str,
    lock_value: str,
    expected_state: str,
) -> None:
    """Test WebSocket message updates entity lock state."""
    handlers = _get_ws_handlers(mock_client)
    await handlers[event](_make_ws_message(event, door_id, lock_value))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == expected_state


@pytest.mark.parametrize(
    "message",
    [
        pytest.param(
            LocationUpdateV2(
                event="access.data.device.location_update_v2",
                data=LocationUpdateData(
                    id="unknown-door",
                    location_type="door",
                    state=LocationUpdateState(lock="unlocked"),
                ),
            ),
            id="unknown_door",
        ),
        pytest.param(
            LocationUpdateV2(
                event="access.data.device.location_update_v2",
                data=LocationUpdateData(
                    id="door-001",
                    location_type="door",
                    state=None,
                ),
            ),
            id="none_state",
        ),
    ],
)
async def test_ws_update_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    message: LocationUpdateV2,
) -> None:
    """Test WebSocket update is ignored for unknown door or None state."""
    handlers = _get_ws_handlers(mock_client)
    await handlers["access.data.device.location_update_v2"](message)
    await hass.async_block_till_done()

    assert hass.states.get("lock.front_door").state == LockState.LOCKED
