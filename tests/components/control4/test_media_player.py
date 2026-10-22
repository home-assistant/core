"""Test Control4 Media Player."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyControl4.error_handling import C4Exception
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.control4.const import SCAN_INTERVAL
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms which should be loaded during the test."""
    return [Platform.MEDIA_PLAYER]


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director", "mock_update_variables")
async def test_media_player_with_and_without_sources(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that rooms with sources create entities and rooms without are skipped."""
    # The default mock_c4_director fixture provides multi-room data:
    # Room 1 has video source, Room 2 has no sources (thermostat-only room)
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_c4_account")
async def test_media_player_setup_recovers_from_failed_first_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_director: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a failed first poll leaves the room unavailable, not missing."""
    mock_c4_director.get_all_item_variable_value.side_effect = C4Exception(
        "director unavailable"
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_c4_director.get_all_item_variable_value.side_effect = None
    mock_c4_director.get_all_item_variable_value.return_value = [
        {"id": 1, "varName": "POWER_STATE", "value": True},
        {"id": 1, "varName": "CURRENT_VOLUME", "value": 50},
        {"id": 1, "varName": "IS_MUTED", "value": False},
        {"id": 1, "varName": "CURRENT_VIDEO_DEVICE", "value": 100},
        {"id": 1, "varName": "CURRENT MEDIA INFO", "value": {}},
        {"id": 1, "varName": "PLAYING", "value": False},
        {"id": 1, "varName": "PAUSED", "value": False},
        {"id": 1, "varName": "STOPPED", "value": False},
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.state == MediaPlayerState.ON
