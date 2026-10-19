"""Test Control4 Media Player."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyControl4.error_handling import C4Exception
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.control4.const import SCAN_INTERVAL
from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import STATE_UNAVAILABLE, Platform
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
    plays 101, then the director resets its source variables on ROOM_OFF, and
    turn_on must still post 101 by id; a name lookup would pick 100.
    """
    mock_room_off_variables[1]["POWER_STATE"] = True
    mock_room_off_variables[1]["CURRENT MEDIA INFO"] = {"mediainfo": {"medSrcDev": 101}}
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.attributes["last_source_id"] == 101

    mock_room_off_variables[1]["POWER_STATE"] = False
    mock_room_off_variables[1]["CURRENT MEDIA INFO"] = {}
    mock_room_off_variables[1]["CURRENT_VIDEO_DEVICE"] = 0
    await _async_refresh(hass, freezer)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.state == MediaPlayerState.OFF
    assert state.attributes["last_source_id"] == 101

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
async def test_media_player_last_source_follows_playing_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_room_off_variables: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the remembered source follows the source being played."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.attributes["last_source_id"] is None

    for source_id in (100, 101):
        mock_room_off_variables[1]["CURRENT MEDIA INFO"] = {
            "mediainfo": {"medSrcDev": source_id}
        }
        await _async_refresh(hass, freezer)

        state = hass.states.get("media_player.living_room")
        assert state is not None
        assert state.attributes["last_source_id"] == source_id


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

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.attributes["last_source_id"] == 101

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
async def test_media_player_last_source_ignores_unknown_video_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_room_off_variables: dict,
) -> None:
    """Test that a video device that is not a room source is not remembered."""
    mock_room_off_variables[1]["CURRENT_VIDEO_DEVICE"] = 999
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.attributes["last_source_id"] is None


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

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.attributes["last_source_id"] == 101

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

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.attributes["last_source_id"] is None

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": "media_player.living_room"},
        blocking=True,
    )

    # Falls through to the room's first video source instead of posting 999.
    mock_c4_room.set_video_and_audio_source.assert_awaited_once_with(100)


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director_duplicate_source_names",
    "mock_room_off_update_variables",
)
async def test_media_player_playing_source_overrides_restored_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_room_off_variables: dict,
) -> None:
    """Test that the source playing at startup wins over the restored one."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State("media_player.living_room", "off"), {"last_source_id": 100})],
    )
    mock_room_off_variables[1]["CURRENT MEDIA INFO"] = {"mediainfo": {"medSrcDev": 101}}
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.attributes["last_source_id"] == 101


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


@pytest.mark.usefixtures(
    "mock_c4_account",
    "mock_c4_director_duplicate_source_names",
    "mock_room_off_update_variables",
)
async def test_media_player_restores_source_saved_while_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_room: MagicMock,
) -> None:
    """Test that a source stored while the room was unavailable is restored.

    Restore storage keeps the extra data even when the entity was unavailable at
    shutdown, and Home Assistant drops the extra state attributes of an
    unavailable entity, so the source has to survive in the extra data alone.
    """
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("media_player.living_room", STATE_UNAVAILABLE),
                {"last_source_id": 101},
            )
        ],
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.attributes["last_source_id"] == 101

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": "media_player.living_room"},
        blocking=True,
    )

    mock_c4_room.set_video_and_audio_source.assert_awaited_once_with(101)


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director_duplicate_source_names")
@patch(
    "homeassistant.components.control4.media_player.update_variables_for_config_entry",
    autospec=True,
)
async def test_media_player_setup_recovers_from_failed_first_poll(
    mock_update_variables: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_room_off_variables: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a failed first poll leaves the room unavailable, not missing."""
    mock_update_variables.side_effect = C4Exception("director unavailable")
    await setup_integration(hass, mock_config_entry)

    # The coordinator has no data yet: the room must still be added, so it can
    # recover on its own, instead of raising while it remembers its source.
    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_update_variables.side_effect = None
    mock_update_variables.return_value = mock_room_off_variables
    await _async_refresh(hass, freezer)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.state == MediaPlayerState.OFF


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director_duplicate_source_names")
@patch(
    "homeassistant.components.control4.media_player.update_variables_for_config_entry",
    autospec=True,
)
async def test_media_player_keeps_last_source_across_unavailable_restart(
    mock_update_variables: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_c4_room: MagicMock,
    mock_room_off_variables: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the last source survives a restart while the room is unavailable.

    This is the case the state attribute cannot cover: Home Assistant drops the
    extra state attributes of an unavailable entity, so the source only lives in
    the restore data when the entity is unavailable at shutdown.
    """
    mock_room_off_variables[1]["POWER_STATE"] = True
    mock_room_off_variables[1]["CURRENT MEDIA INFO"] = {"mediainfo": {"medSrcDev": 101}}
    mock_update_variables.return_value = mock_room_off_variables
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.attributes["last_source_id"] == 101

    # The director stops answering, so the room goes unavailable, and it is off
    # when the director is next read.
    mock_room_off_variables[1]["POWER_STATE"] = False
    mock_room_off_variables[1]["CURRENT MEDIA INFO"] = {}
    mock_update_variables.side_effect = C4Exception("director unavailable")
    await _async_refresh(hass, freezer)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Home Assistant restarts while the director is still unreachable, and the
    # director comes back before the room is used.
    await async_mock_restore_state_shutdown_restart(hass)
    mock_update_variables.side_effect = None
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await _async_refresh(hass, freezer)

    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.state == MediaPlayerState.OFF
    assert state.attributes["last_source_id"] == 101

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": "media_player.living_room"},
        blocking=True,
    )

    mock_c4_room.set_video_and_audio_source.assert_awaited_once_with(101)
