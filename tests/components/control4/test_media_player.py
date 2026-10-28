"""Test Control4 Media Player."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.control4.const import SCAN_INTERVAL
from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, State
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


@pytest.mark.usefixtures(
    "mock_c4_account", "mock_c4_director", "mock_room_off_update_variables"
)
async def test_media_player_room_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_room: MagicMock,
    mock_room_off_variables: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a room which is off is off, and can be turned on."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.state == MediaPlayerState.OFF
    assert state.attributes["supported_features"] & MediaPlayerEntityFeature.TURN_ON

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": "media_player.living_room"},
        blocking=True,
    )

    # A room is started by selecting a source, the way the Control4 app does it:
    # room 1 has a single video source, the TV.
    mock_c4_room.set_video_and_audio_source.assert_awaited_once_with(100)
    mock_c4_room.set_room_off.assert_not_called()

    # Once the director reports the room as powered, the state follows.
    mock_room_off_variables[1]["POWER_STATE"] = True
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.state == MediaPlayerState.ON


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director_audio_first_mixed_sources",
    "mock_room_off_update_variables",
)
async def test_media_player_turn_on_prefers_video_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_room: MagicMock,
) -> None:
    """Test that a room that never played starts with its first video source.

    Room 1 has an audio source (200) listed before a video source (100), so the
    fallback must skip the first (audio) source and start the video one.
    """
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": "media_player.living_room"},
        blocking=True,
    )

    mock_c4_room.set_video_and_audio_source.assert_awaited_once_with(100)
    mock_c4_room.set_audio_source.assert_not_called()


@pytest.mark.usefixtures(
    "mock_c4_account", "mock_c4_director_audio_room", "mock_room_off_update_variables"
)
async def test_media_player_turn_on_audio_only_room(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_room: MagicMock,
) -> None:
    """Test that a listen-only room is started with an audio source selection."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": "media_player.living_room"},
        blocking=True,
    )

    mock_c4_room.set_audio_source.assert_awaited_once_with(100)
    mock_c4_room.set_video_and_audio_source.assert_not_called()


async def _async_refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the coordinator poll the director again."""
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director_duplicate_source_names",
    "mock_room_off_update_variables",
)
async def test_media_player_turn_on_restarts_last_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_room: MagicMock,
    mock_room_off_variables: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the source survives the room being turned off.

    Room 1 has two video sources both named "TV" (ids 100 and 101). The room
    starts on 100 and switches to 101, then the director resets its source
    variables on ROOM_OFF, and turn_on must still post 101 by id; a name lookup
    would pick 100.
    """
    mock_room_off_variables[1]["POWER_STATE"] = True
    mock_room_off_variables[1]["CURRENT MEDIA INFO"] = {"mediainfo": {"medSrcDev": 100}}
    await setup_integration(hass, mock_config_entry)

    mock_room_off_variables[1]["CURRENT MEDIA INFO"] = {"mediainfo": {"medSrcDev": 101}}
    await _async_refresh(hass, freezer)

    mock_room_off_variables[1]["POWER_STATE"] = False
    mock_room_off_variables[1]["CURRENT MEDIA INFO"] = {}
    mock_room_off_variables[1]["CURRENT_VIDEO_DEVICE"] = 0
    await _async_refresh(hass, freezer)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.state == MediaPlayerState.OFF

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": "media_player.living_room"},
        blocking=True,
    )

    mock_c4_room.set_video_and_audio_source.assert_awaited_once_with(101)


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director_duplicate_source_names",
    "mock_room_off_update_variables",
)
async def test_media_player_last_source_falls_back_to_video_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_room: MagicMock,
    mock_room_off_variables: dict,
) -> None:
    """Test that a room without media info is tracked by its video device."""
    mock_room_off_variables[1]["POWER_STATE"] = True
    mock_room_off_variables[1]["CURRENT_VIDEO_DEVICE"] = 101
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": "media_player.living_room"},
        blocking=True,
    )

    mock_c4_room.set_video_and_audio_source.assert_awaited_once_with(101)


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director_duplicate_source_names",
    "mock_room_off_update_variables",
)
async def test_media_player_turn_on_restores_last_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_room: MagicMock,
) -> None:
    """Test that the last source is restored and used after a restart."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State("media_player.living_room", "off"), {"last_source_id": 101})],
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": "media_player.living_room"},
        blocking=True,
    )

    mock_c4_room.set_video_and_audio_source.assert_awaited_once_with(101)


@pytest.mark.usefixtures(
    "mock_c4_account", "mock_c4_director", "mock_room_off_update_variables"
)
async def test_media_player_turn_on_ignores_restored_unknown_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_room: MagicMock,
) -> None:
    """Test that a restored source the room no longer has is ignored."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State("media_player.living_room", "off"), {"last_source_id": 999})],
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": "media_player.living_room"},
        blocking=True,
    )

    # Falls through to the room's first video source instead of posting 999.
    mock_c4_room.set_video_and_audio_source.assert_awaited_once_with(100)


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director", "mock_update_variables")
async def test_media_player_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_room: MagicMock,
) -> None:
    """Test that turning off a room turns the room off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "media_player",
        "turn_off",
        {"entity_id": "media_player.living_room"},
        blocking=True,
    )

    mock_c4_room.set_room_off.assert_awaited_once()
    mock_c4_room.set_video_and_audio_source.assert_not_called()
