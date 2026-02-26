"""Tests for the syncthing integration setup and client."""

import asyncio
from typing import Any
from unittest.mock import patch

from aiosyncthing.exceptions import SyncthingError

from homeassistant.components.syncthing.const import (
    DEVICE_CONNECTED_RECEIVED,
    DOMAIN,
    FOLDER_SUMMARY_RECEIVED,
    INITIAL_EVENTS_READY,
    RECONNECT_INTERVAL,
    SERVER_AVAILABLE,
    SERVER_UNAVAILABLE,
    STATE_CHANGED_RECEIVED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import dispatcher
from homeassistant.util import dt as dt_util

from . import (
    DEVICE_ID,
    FOLDER_ID,
    MOCK_DEVICE_CONNECTED_EVENT,
    MOCK_DEVICE_DISCONNECTED_EVENT,
    MOCK_FOLDER_SUMMARY_EVENT,
    MOCK_STATE_CHANGED_EVENT,
    SERVER_ID,
    create_mock_syncthing_client,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_syncthing_client_event_listener(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test SyncthingClient event listener handles device and folder events."""
    events = [
        MOCK_DEVICE_CONNECTED_EVENT,
        MOCK_FOLDER_SUMMARY_EVENT,
        MOCK_STATE_CHANGED_EVENT,
    ]

    device_connected_calls = []
    folder_summary_calls = []
    state_changed_calls = []

    async def device_connected_handler(event: dict[str, Any]) -> None:
        """Handle device connected event."""
        device_connected_calls.append(event)

    async def folder_summary_handler(event: dict[str, Any]) -> None:
        """Handle folder summary event."""
        folder_summary_calls.append(event)

    async def state_changed_handler(event: dict[str, Any]) -> None:
        """Handle state changed event."""
        state_changed_calls.append(event)

    dispatcher.async_dispatcher_connect(
        hass,
        f"{DEVICE_CONNECTED_RECEIVED}-{SERVER_ID}-{DEVICE_ID}",
        device_connected_handler,
    )
    dispatcher.async_dispatcher_connect(
        hass,
        f"{FOLDER_SUMMARY_RECEIVED}-{SERVER_ID}-{FOLDER_ID}",
        folder_summary_handler,
    )
    dispatcher.async_dispatcher_connect(
        hass,
        f"{STATE_CHANGED_RECEIVED}-{SERVER_ID}-{FOLDER_ID}",
        state_changed_handler,
    )

    async def mock_listen():
        """Mock events.listen that yields all events and then loops indefinitely without blocking."""
        for event in events:
            await asyncio.sleep(0)
            yield event
        while True:
            await asyncio.sleep(0)
            yield {"type": "unknown"}

    mock_syncthing = create_mock_syncthing_client()
    mock_syncthing.events.listen = mock_listen
    mock_syncthing.events.last_seen_id = 10

    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()
    await asyncio.sleep(0)
    await hass.async_block_till_done()

    assert len(device_connected_calls) == 1
    assert device_connected_calls[0] == MOCK_DEVICE_CONNECTED_EVENT

    assert len(folder_summary_calls) == 1
    assert folder_summary_calls[0] == MOCK_FOLDER_SUMMARY_EVENT

    assert len(state_changed_calls) == 1
    assert state_changed_calls[0] == MOCK_STATE_CHANGED_EVENT


async def test_syncthing_client_stores_initial_events(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test SyncthingClient stores initial device events (last_seen_id = 0)."""
    initial_events = [
        MOCK_DEVICE_CONNECTED_EVENT,
        MOCK_DEVICE_DISCONNECTED_EVENT,
    ]

    mock_syncthing = create_mock_syncthing_client()
    mock_syncthing.events.last_seen_id = 0

    async def mock_listen():
        """Mock events.listen that yields all events and then loops indefinitely without blocking."""
        for event in initial_events:
            await asyncio.sleep(0)
            yield event
        mock_syncthing.events.last_seen_id = 10
        while True:
            await asyncio.sleep(0)
            yield None

    mock_syncthing.events.listen = mock_listen

    initial_events_ready_calls = []

    async def initial_events_ready_handler() -> None:
        """Handle initial events ready signal."""
        initial_events_ready_calls.append(True)

    dispatcher.async_dispatcher_connect(
        hass,
        f"{INITIAL_EVENTS_READY}-{SERVER_ID}",
        initial_events_ready_handler,
    )

    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

        await asyncio.sleep(0.1)
        await hass.async_block_till_done()

    syncthing = hass.data[DOMAIN][entry.entry_id]
    stored_events = syncthing.get_initial_events()

    assert len(stored_events) == 2
    assert stored_events[0] == MOCK_DEVICE_CONNECTED_EVENT
    assert stored_events[1] == MOCK_DEVICE_DISCONNECTED_EVENT

    assert len(initial_events_ready_calls) == 1


async def test_syncthing_client_reconnect_on_error(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test SyncthingClient reconnects when server becomes unavailable."""
    call_count = 0

    async def mock_listen():
        """Mock listen that raises error first, then succeeds."""
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise SyncthingError("Connection lost")
        while True:
            await asyncio.sleep(0.1)
            yield MOCK_STATE_CHANGED_EVENT

    mock_syncthing = create_mock_syncthing_client()
    mock_syncthing.events.last_seen_id = 10
    mock_syncthing.events.listen = mock_listen

    server_unavailable_calls = []
    server_available_calls = []

    async def server_unavailable_handler() -> None:
        """Handle server unavailable signal."""
        server_unavailable_calls.append(True)

    async def server_available_handler() -> None:
        """Handle server available signal."""
        server_available_calls.append(True)

    dispatcher.async_dispatcher_connect(
        hass,
        f"{SERVER_UNAVAILABLE}-{SERVER_ID}",
        server_unavailable_handler,
    )
    dispatcher.async_dispatcher_connect(
        hass,
        f"{SERVER_AVAILABLE}-{SERVER_ID}",
        server_available_handler,
    )

    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

        await asyncio.sleep(0.2)
        await hass.async_block_till_done()

    assert len(server_unavailable_calls) >= 1
    assert len(server_available_calls) == 0

    future = dt_util.utcnow() + RECONNECT_INTERVAL
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert len(server_available_calls) >= 1
