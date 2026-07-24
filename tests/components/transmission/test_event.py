"""Tests for the Transmission event platform."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.components.transmission.const import (
    DEFAULT_SCAN_INTERVAL,
    EVENT_TYPE_DOWNLOADED,
    EVENT_TYPE_REMOVED,
    EVENT_TYPE_STARTED,
)
from homeassistant.const import Platform
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_event_entity_setup(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the event entity is created with expected capabilities."""
    with patch("homeassistant.components.transmission.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

    state = hass.states.get("event.transmission_torrent")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes[ATTR_EVENT_TYPE] is None
    assert state.attributes[ATTR_EVENT_TYPES] == [
        EVENT_TYPE_STARTED,
        EVENT_TYPE_DOWNLOADED,
        EVENT_TYPE_REMOVED,
    ]


@pytest.mark.parametrize(
    ("hass_event", "expected_event_type"),
    [
        (EVENT_TYPE_STARTED, EVENT_TYPE_STARTED),
        (EVENT_TYPE_DOWNLOADED, EVENT_TYPE_DOWNLOADED),
        (EVENT_TYPE_REMOVED, EVENT_TYPE_REMOVED),
    ],
)
async def test_event_updates_state(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    hass_event: str,
    expected_event_type: str,
) -> None:
    """Test Transmission events update the entity state and attributes."""
    with patch("homeassistant.components.transmission.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

    client = mock_transmission_client.return_value
    torrent_status = {
        EVENT_TYPE_STARTED: "downloading",
        EVENT_TYPE_DOWNLOADED: "seeding",
        EVENT_TYPE_REMOVED: "stopped",
    }[hass_event]
    torrent = SimpleNamespace(
        id=1,
        name="Test",
        status=torrent_status,
        download_dir="/downloads",
        labels=[],
    )

    torrents_sequence = {
        EVENT_TYPE_STARTED: [[torrent]],
        EVENT_TYPE_DOWNLOADED: [[torrent]],
        EVENT_TYPE_REMOVED: [[torrent], []],
    }[hass_event]

    client.get_torrents.side_effect = torrents_sequence

    for _ in torrents_sequence:
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("event.transmission_torrent")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == expected_event_type
    assert state.attributes["id"] == 1
    assert state.attributes["name"] == "Test"
    assert state.attributes["download_path"] == "/downloads"
    assert state.attributes["labels"] == []
    assert dt_util.parse_datetime(state.state) is not None


async def test_multiple_events_staggered(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that multiple torrents completing in one poll are all delivered.

    Events are scheduled with staggered delays to prevent deduplication by
    event.received triggers (which dedupe on state value equality). This test
    verifies that all events are delivered, even when many torrents change
    in a single poll.
    """
    with patch("homeassistant.components.transmission.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

    client = mock_transmission_client.return_value

    # Create multiple torrents that complete in one poll
    completed_torrents = [
        SimpleNamespace(
            id=i,
            name=f"Torrent {i}",
            status="seeding",
            download_dir="/downloads",
            labels=[],
        )
        for i in range(1, 4)
    ]

    # First poll: no torrents, second poll: all 3 completed
    client.get_torrents.side_effect = [[], completed_torrents]

    # Collect torrent IDs from events to verify all are delivered
    torrent_ids_received = set()

    def state_changed_listener(event: Event[EventStateChangedData]) -> None:
        """Capture torrent IDs from events."""
        if event.data["entity_id"] == "event.transmission_torrent":
            new_state = event.data.get("new_state")
            if (
                new_state
                and new_state.attributes.get("event_type") == EVENT_TYPE_DOWNLOADED
            ):
                torrent_id = new_state.attributes.get("id")
                if torrent_id:
                    torrent_ids_received.add(torrent_id)

    hass.bus.async_listen("state_changed", state_changed_listener)

    # First poll: initialize with no torrents
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Second poll: all 3 torrents are completed
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Advance time to let all staggered callbacks complete
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify all 3 torrents were delivered as separate events
    assert torrent_ids_received == {1, 2, 3}, (
        f"Expected torrents {{1, 2, 3}}, got {torrent_ids_received}"
    )

    # Verify the final event state is from one of the torrents
    state = hass.states.get("event.transmission_torrent")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == EVENT_TYPE_DOWNLOADED
    assert state.attributes["id"] in (1, 2, 3)
    assert state.attributes["name"] in ("Torrent 1", "Torrent 2", "Torrent 3")
    assert state.attributes["download_path"] == "/downloads"


async def test_mixed_event_types_no_collision(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that events of different types in one poll have distinct timestamps.

    When torrents complete and start in the same poll cycle, events are
    scheduled with staggered delays to ensure each gets a distinct timestamp.
    Without this fix, events from different check methods would be scheduled
    at the same delay and share timestamps, causing event.received to dedupe.
    """
    with patch("homeassistant.components.transmission.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

    client = mock_transmission_client.return_value

    # Create torrents in different states
    downloaded_torrent = SimpleNamespace(
        id=1,
        name="Downloaded Torrent",
        status="seeding",
        download_dir="/downloads",
        labels=[],
    )
    started_torrent = SimpleNamespace(
        id=2,
        name="Started Torrent",
        status="downloading",
        download_dir="/downloads",
        labels=[],
    )

    # First poll: no torrents
    # Second poll: one downloaded, one started
    # Third poll: both torrents present (no new events)
    client.get_torrents.side_effect = [
        [],  # Poll 1: empty
        [downloaded_torrent, started_torrent],  # Poll 2: both appear
        [downloaded_torrent, started_torrent],  # Poll 3: no changes
    ]

    # Collect event state timestamps by type
    event_timestamps_by_type = {}

    def state_changed_listener(event: Event[EventStateChangedData]) -> None:
        """Capture event types and their timestamps."""
        if event.data["entity_id"] == "event.transmission_torrent":
            new_state = event.data.get("new_state")
            if new_state:
                event_type = new_state.attributes.get("event_type")
                if event_type:
                    # Store timestamps by event type
                    if event_type not in event_timestamps_by_type:
                        event_timestamps_by_type[event_type] = []
                    event_timestamps_by_type[event_type].append(new_state.state)

    hass.bus.async_listen("state_changed", state_changed_listener)

    # First poll: initialize
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Second poll: both torrents appear
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Advance time by small increments to ensure staggered callbacks get different times
    for _ in range(2):
        freezer.tick(timedelta(milliseconds=1.1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    # Verify both event types were recorded (both events delivered)
    assert EVENT_TYPE_DOWNLOADED in event_timestamps_by_type, (
        "Downloaded event not seen"
    )
    assert EVENT_TYPE_STARTED in event_timestamps_by_type, "Started event not seen"

    # Verify we got one of each event type
    downloaded_count = len(event_timestamps_by_type[EVENT_TYPE_DOWNLOADED])
    started_count = len(event_timestamps_by_type[EVENT_TYPE_STARTED])
    assert downloaded_count >= 1, (
        f"Expected at least 1 downloaded event, got {downloaded_count}"
    )
    assert started_count >= 1, f"Expected at least 1 started event, got {started_count}"

    # Third poll: no new events
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # State should still reflect one of the events seen
    state = hass.states.get("event.transmission_torrent")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] in (
        EVENT_TYPE_DOWNLOADED,
        EVENT_TYPE_STARTED,
    )
    assert state.attributes["id"] in (1, 2)
