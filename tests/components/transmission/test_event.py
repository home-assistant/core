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
    """Test that multiple torrents completing in one poll are delivered without deduplication."""
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

    # Collect torrent IDs from state changes for the event entity
    torrent_ids_seen = set()

    def state_changed_listener(event: Event[EventStateChangedData]) -> None:
        """Capture torrent IDs from state changes."""
        if event.data["entity_id"] == "event.transmission_torrent":
            new_state = event.data.get("new_state")
            if (
                new_state
                and new_state.attributes.get("event_type") == EVENT_TYPE_DOWNLOADED
            ):
                torrent_id = new_state.attributes.get("id")
                if torrent_id:
                    torrent_ids_seen.add(torrent_id)

    hass.bus.async_listen("state_changed", state_changed_listener)

    # First poll: initialize with no torrents
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Second poll: all 3 torrents are completed
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Wait for all staggered events to complete
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify all 3 events fired (each torrent ID was seen)
    assert torrent_ids_seen == {1, 2, 3}, (
        f"Not all torrents delivered: expected {{1, 2, 3}}, got {torrent_ids_seen}"
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
    """Test that events of different types in one poll don't collide.

    When torrents complete and start in the same poll cycle, events are
    scheduled with cumulative delays to prevent deduplication. Without the
    fix, events from different check methods would share the same delay
    (both starting at 0.0s) and collide, causing deduplication.
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

    # Track all event types and their torrent IDs
    event_types_seen = {}

    def state_changed_listener(event: Event[EventStateChangedData]) -> None:
        """Capture event types seen with their torrent IDs."""
        if event.data["entity_id"] == "event.transmission_torrent":
            new_state = event.data.get("new_state")
            if new_state and new_state.attributes.get("id"):
                torrent_id = new_state.attributes.get("id")
                event_type = new_state.attributes.get("event_type")
                # Store as: {torrent_id: event_type}
                event_types_seen[torrent_id] = event_type

    hass.bus.async_listen("state_changed", state_changed_listener)

    # First poll: initialize
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Second poll: both torrents appear
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Wait for staggered events to complete
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify both events were delivered without collision
    # (both should have fired, not one deduplicated away due to same timestamp)
    assert event_types_seen.get(1) == EVENT_TYPE_DOWNLOADED, (
        "Downloaded event not delivered for torrent 1"
    )
    assert event_types_seen.get(2) == EVENT_TYPE_STARTED, (
        "Started event not delivered for torrent 2"
    )

    # Third poll: no new events
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # State should still reflect the last event seen
    state = hass.states.get("event.transmission_torrent")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] in (
        EVENT_TYPE_DOWNLOADED,
        EVENT_TYPE_STARTED,
    )
    assert state.attributes["id"] in (1, 2)
