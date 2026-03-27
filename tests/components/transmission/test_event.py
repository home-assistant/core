"""Tests for the Transmission event platform."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import event as event_component
from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.components.transmission.const import (
    EVENT_DOWNLOADED_TORRENT,
    EVENT_REMOVED_TORRENT,
    EVENT_STARTED_TORRENT,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry


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
        EVENT_STARTED_TORRENT,
        EVENT_DOWNLOADED_TORRENT,
        EVENT_REMOVED_TORRENT,
    ]


@pytest.mark.parametrize(
    ("hass_event", "expected_event_type"),
    [
        (EVENT_STARTED_TORRENT, EVENT_STARTED_TORRENT),
        (EVENT_DOWNLOADED_TORRENT, EVENT_DOWNLOADED_TORRENT),
        (EVENT_REMOVED_TORRENT, EVENT_REMOVED_TORRENT),
    ],
)
async def test_event_updates_state(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_event: str,
    expected_event_type: str,
) -> None:
    """Test Transmission events update the entity state and attributes."""
    with patch("homeassistant.components.transmission.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    component = hass.data[event_component.DATA_COMPONENT]
    entity = component.get_entity("event.transmission_torrent")
    assert entity is not None

    client = mock_transmission_client.return_value
    torrent_status = {
        EVENT_STARTED_TORRENT: "downloading",
        EVENT_DOWNLOADED_TORRENT: "seeding",
        EVENT_REMOVED_TORRENT: "stopped",
    }[hass_event]
    torrent = SimpleNamespace(
        id=1,
        name="Test",
        status=torrent_status,
        download_dir="/downloads",
        labels=[],
    )

    torrents_sequence = {
        EVENT_STARTED_TORRENT: [[torrent]],
        EVENT_DOWNLOADED_TORRENT: [[torrent]],
        EVENT_REMOVED_TORRENT: [[torrent], []],
    }[hass_event]

    client.get_torrents.side_effect = torrents_sequence

    for _ in torrents_sequence:
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("event.transmission_torrent")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == expected_event_type
    assert state.attributes["id"] == 1
    assert state.attributes["name"] == "Test"
    assert state.attributes["download_path"] == "/downloads"
    assert state.attributes["labels"] == []
    assert dt_util.parse_datetime(state.state) is not None


async def test_unknown_event_ignored(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unknown event does not update the entity state and logs."""
    with patch("homeassistant.components.transmission.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)

    initial_state = hass.states.get("event.transmission_torrent")
    assert initial_state is not None

    coordinator = mock_config_entry.runtime_data
    component = hass.data[event_component.DATA_COMPONENT]
    entity = component.get_entity("event.transmission_torrent")
    assert entity is not None
    coordinator.async_add_event_listener(entity._handle_event, entity.unique_id)

    caplog.set_level(logging.WARNING, "homeassistant.components.transmission.event")

    client = mock_transmission_client.return_value
    torrent = SimpleNamespace(
        id=2,
        name="Unknown",
        status="downloading",
        download_dir="/downloads",
        labels=[],
    )
    client.get_torrents.side_effect = [[torrent]]

    with patch(
        "homeassistant.components.transmission.coordinator.EVENT_STARTED_TORRENT",
        "transmission_unknown_event",
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    await hass.async_block_till_done()

    state = hass.states.get("event.transmission_torrent")
    assert state is not None
    assert state.state == initial_state.state
    assert state.attributes[ATTR_EVENT_TYPE] is None
    assert "Event type transmission_unknown_event is not known" in caplog.text
