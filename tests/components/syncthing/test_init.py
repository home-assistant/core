"""Tests for the syncthing integration setup and client."""

import asyncio
from unittest.mock import MagicMock, patch

from aiosyncthing.exceptions import SyncthingError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.syncthing.const import (
    DOMAIN,
    EVENTS,
    RECONNECT_INTERVAL,
    SERVER_AVAILABLE,
    SERVER_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import dispatcher

from . import SERVER_ID

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
)


async def test_syncthing_client_reconnect_on_error(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing_client: MagicMock,
    freezer: FrozenDateTimeFactory,
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
            yield await hass.async_add_executor_job(
                load_json_object_fixture, "state_changed_event.json", DOMAIN
            )

    mock_syncthing_client.events.last_seen_id = 10
    mock_syncthing_client.events.listen = mock_listen

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
        autospec=True,
    ) as mock_class:
        mock_class.return_value = mock_syncthing_client
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(server_unavailable_calls) >= 1
        assert len(server_available_calls) == 0

        freezer.tick(RECONNECT_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert len(server_available_calls) >= 1

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "event_fixture",
    [
        "folder_summary_event.json",
        "state_changed_event.json",
        "folder_paused_event.json",
    ],
)
async def test_client_dispatches_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing_client: MagicMock,
    event_fixture: str,
) -> None:
    """Test SyncthingClient dispatches the expected signal for syncthing events."""
    event = await hass.async_add_executor_job(
        load_json_object_fixture, event_fixture, DOMAIN
    )

    async def mock_listen():
        yield event
        await asyncio.Event().wait()

    mock_syncthing_client.events.listen = mock_listen
    mock_syncthing_client.events.last_seen_id = 10

    folder = event["data"].get("folder") or event["data"]["id"]
    signal = f"{EVENTS[event['type']]}-{SERVER_ID}-{folder}"

    received = asyncio.Event()
    captured: list[dict] = []

    @callback
    def handler(received_event: dict) -> None:
        captured.append(received_event)
        received.set()

    dispatcher.async_dispatcher_connect(hass, signal, handler)
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        autospec=True,
    ) as mock_class:
        mock_class.return_value = mock_syncthing_client
        assert await hass.config_entries.async_setup(entry.entry_id)

    async with asyncio.timeout(5):
        await received.wait()

    assert captured == [event]
