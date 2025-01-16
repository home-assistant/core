"""Tests for the Heos Media Player platform."""

from collections.abc import Sequence
from datetime import timedelta

from pyheos import (
    AddCriteriaType,
    CommandFailedError,
    Heos,
    HeosError,
    MediaItem,
    PlayerUpdateResult,
    PlayState,
    SignalHeosEvent,
    SignalType,
    const,
)
import pytest

from homeassistant.components.heos.const import DOMAIN
from homeassistant.components.heos.media_player import BASE_SUPPORTED_FEATURES
from homeassistant.components.media_player import (
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_JOIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SERVICE_UNJOIN,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_SHUFFLE_SET,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    STATE_IDLE,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import MockHeosConfigEntry

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("controller")
async def test_state_attributes(
    hass: HomeAssistant, config_entry: MockHeosConfigEntry
) -> None:
    """Tests the state attributes."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.25
    assert not state.attributes[ATTR_MEDIA_VOLUME_MUTED]
    assert state.attributes[ATTR_MEDIA_CONTENT_ID] == "1"
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert ATTR_MEDIA_DURATION not in state.attributes
    assert ATTR_MEDIA_POSITION not in state.attributes
    assert state.attributes[ATTR_MEDIA_TITLE] == "Song"
    assert state.attributes[ATTR_MEDIA_ARTIST] == "Artist"
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "Album"
    assert not state.attributes[ATTR_MEDIA_SHUFFLE]
    assert state.attributes["media_album_id"] == 1
    assert state.attributes["media_queue_id"] == 1
    assert state.attributes["media_source_id"] == 1
    assert state.attributes["media_station"] == "Station Name"
    assert state.attributes["media_type"] == "Station"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Test Player"
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | BASE_SUPPORTED_FEATURES
    )
    assert ATTR_INPUT_SOURCE not in state.attributes
    assert (
        state.attributes[ATTR_INPUT_SOURCE_LIST]
        == config_entry.runtime_data.source_list
    )


async def test_updates_from_signals(
    hass: HomeAssistant, config_entry: MockHeosConfigEntry, controller: Heos
) -> None:
    """Tests dispatched signals update player."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]

    # Test player does not update for other players
    player.state = PlayState.PLAY
    await player.heos.dispatcher.wait_send(
        SignalType.PLAYER_EVENT, 2, const.EVENT_PLAYER_STATE_CHANGED
    )
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE

    # Test player_update standard events
    player.state = PlayState.PLAY
    await player.heos.dispatcher.wait_send(
        SignalType.PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_PLAYING

    # Test player_update progress events
    player.now_playing_media.duration = 360000
    player.now_playing_media.current_position = 1000
    await player.heos.dispatcher.wait_send(
        SignalType.PLAYER_EVENT,
        player.player_id,
        const.EVENT_PLAYER_NOW_PLAYING_PROGRESS,
    )
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] is not None
    assert state.attributes[ATTR_MEDIA_DURATION] == 360
    assert state.attributes[ATTR_MEDIA_POSITION] == 1


async def test_updates_from_connection_event(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    change_data_mapped_ids: PlayerUpdateResult,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests player updates from connection event after connection failure."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE

    # Disconnected
    controller.load_players.reset_mock()
    player.available = False
    await player.heos.dispatcher.wait_send(
        SignalType.HEOS_EVENT, SignalHeosEvent.DISCONNECTED
    )
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_UNAVAILABLE
    assert controller.load_players.call_count == 0
    controller.get_groups.reset_mock()
    controller.get_input_sources.reset_mock()
    controller.get_favorites.reset_mock()

    # Connected
    player.available = True
    controller.load_players.return_value = change_data_mapped_ids
    await player.heos.dispatcher.wait_send(
        SignalType.HEOS_EVENT, SignalHeosEvent.CONNECTED
    )
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE
    assert controller.load_players.call_count == 1
    assert controller.get_groups.call_count == 1
    assert controller.get_input_sources.call_count == 1
    assert controller.get_favorites.call_count == 1

    # Connected handles refresh failure
    controller.load_players.reset_mock()
    controller.load_players.side_effect = CommandFailedError(None, "Failure", 1)
    player.available = True
    await player.heos.dispatcher.wait_send(
        SignalType.HEOS_EVENT, SignalHeosEvent.CONNECTED
    )
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE
    assert controller.load_players.call_count == 1
    assert "Unable to update players" in caplog.text


@pytest.mark.parametrize(
    "event", [const.EVENT_SOURCES_CHANGED, const.EVENT_USER_CHANGED]
)
async def test_sources_updates_from_events(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    input_sources: Sequence[MediaItem],
    event: str,
) -> None:
    """Tests player updates from changes in sources list."""
    config_entry.add_to_hass(hass)
    controller.get_input_sources.return_value = []
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    state = hass.states.get("media_player.test_player")
    assert len(state.attributes[ATTR_INPUT_SOURCE_LIST]) == 2

    controller.get_input_sources.return_value = input_sources
    await player.heos.dispatcher.wait_send(SignalType.CONTROLLER_EVENT, event, {})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert len(state.attributes[ATTR_INPUT_SOURCE_LIST]) == 3


async def test_updates_from_players_changed(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    change_data: PlayerUpdateResult,
) -> None:
    """Test player updates from changes to available players."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]

    assert hass.states.get("media_player.test_player").state == STATE_IDLE
    player.state = PlayState.PLAY
    await player.heos.dispatcher.wait_send(
        SignalType.CONTROLLER_EVENT, const.EVENT_PLAYERS_CHANGED, change_data
    )
    assert hass.states.get("media_player.test_player").state == STATE_PLAYING


async def test_updates_from_players_changed_new_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    change_data_mapped_ids: PlayerUpdateResult,
) -> None:
    """Test player updates from changes to available players."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]

    # Assert device registry matches current id
    assert device_registry.async_get_device(identifiers={(DOMAIN, "1")})
    # Assert entity registry matches current id
    assert (
        entity_registry.async_get_entity_id(MEDIA_PLAYER_DOMAIN, DOMAIN, "1")
        == "media_player.test_player"
    )

    await player.heos.dispatcher.wait_send(
        SignalType.CONTROLLER_EVENT,
        const.EVENT_PLAYERS_CHANGED,
        change_data_mapped_ids,
    )
    # Assert device registry identifiers were updated
    assert len(device_registry.devices) == 2
    assert device_registry.async_get_device(identifiers={(DOMAIN, "101")})
    # Assert entity registry unique id was updated
    assert len(entity_registry.entities) == 2
    assert (
        entity_registry.async_get_entity_id(MEDIA_PLAYER_DOMAIN, DOMAIN, "101")
        == "media_player.test_player"
    )


async def test_updates_from_groups_changed(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
) -> None:
    """Test player updates from changes to groups."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    # Assert current state
    assert hass.states.get("media_player.test_player").attributes[
        ATTR_GROUP_MEMBERS
    ] == ["media_player.test_player", "media_player.test_player_2"]
    assert hass.states.get("media_player.test_player_2").attributes[
        ATTR_GROUP_MEMBERS
    ] == ["media_player.test_player", "media_player.test_player_2"]

    # Clear group information
    controller._groups = {}
    controller.get_groups.return_value = {}
    for player in controller.players.values():
        player.group_id = None
    await controller.dispatcher.wait_send(
        SignalType.CONTROLLER_EVENT, const.EVENT_GROUPS_CHANGED, None
    )

    # Assert groups changed
    assert (
        hass.states.get("media_player.test_player").attributes[ATTR_GROUP_MEMBERS]
        is None
    )
    assert (
        hass.states.get("media_player.test_player_2").attributes[ATTR_GROUP_MEMBERS]
        is None
    )


async def test_clear_playlist(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the clear playlist service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_CLEAR_PLAYLIST,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
        assert player.clear_queue.call_count == 1
        player.clear_queue.reset_mock()
        player.clear_queue.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to clear playlist: Failure (1)" in caplog.text


async def test_pause(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the pause service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PAUSE,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
        assert player.pause.call_count == 1
        player.pause.reset_mock()
        player.pause.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to pause: Failure (1)" in caplog.text


async def test_play(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the play service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PLAY,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
        assert player.play.call_count == 1
        player.play.reset_mock()
        player.play.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to play: Failure (1)" in caplog.text


async def test_previous_track(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the previous track service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
        assert player.play_previous.call_count == 1
        player.play_previous.reset_mock()
        player.play_previous.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to move to previous track: Failure (1)" in caplog.text


async def test_next_track(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the next track service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
        assert player.play_next.call_count == 1
        player.play_next.reset_mock()
        player.play_next.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to move to next track: Failure (1)" in caplog.text


async def test_stop(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the stop service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_STOP,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
        assert player.stop.call_count == 1
        player.stop.reset_mock()
        player.stop.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to stop: Failure (1)" in caplog.text


async def test_volume_mute(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the volume mute service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_MUTE,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_MUTED: True},
            blocking=True,
        )
        assert player.set_mute.call_count == 1
        player.set_mute.reset_mock()
        player.set_mute.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to set mute: Failure (1)" in caplog.text


async def test_shuffle_set(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the shuffle set service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SHUFFLE_SET,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_SHUFFLE: True},
            blocking=True,
        )
        player.set_play_mode.assert_called_once_with(player.repeat, True)
        player.set_play_mode.reset_mock()
        player.set_play_mode.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to set shuffle: Failure (1)" in caplog.text


async def test_volume_set(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the volume set service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_SET,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_LEVEL: 1},
            blocking=True,
        )
        player.set_volume.assert_called_once_with(100)
        player.set_volume.reset_mock()
        player.set_volume.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to set volume level: Failure (1)" in caplog.text


async def test_select_favorite(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    favorites: dict[int, MediaItem],
) -> None:
    """Tests selecting a music service favorite and state."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # Test set music service preset
    favorite = favorites[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_INPUT_SOURCE: favorite.name},
        blocking=True,
    )
    player.play_preset_station.assert_called_once_with(1)
    # Test state is matched by station name
    player.now_playing_media.station = favorite.name
    player.heos.dispatcher.send(
        SignalType.PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_INPUT_SOURCE] == favorite.name


async def test_select_radio_favorite(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    favorites: dict[int, MediaItem],
) -> None:
    """Tests selecting a radio favorite and state."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # Test set radio preset
    favorite = favorites[2]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_INPUT_SOURCE: favorite.name},
        blocking=True,
    )
    player.play_preset_station.assert_called_once_with(2)
    # Test state is matched by album id
    player.now_playing_media.station = "Classical"
    player.now_playing_media.album_id = favorite.media_id
    player.heos.dispatcher.send(
        SignalType.PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_INPUT_SOURCE] == favorite.name


async def test_select_radio_favorite_command_error(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    favorites: dict[int, MediaItem],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests command error logged when playing favorite."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # Test set radio preset
    favorite = favorites[2]
    player.play_preset_station.side_effect = CommandFailedError(None, "Failure", 1)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_INPUT_SOURCE: favorite.name},
        blocking=True,
    )
    player.play_preset_station.assert_called_once_with(2)
    assert "Unable to select source: Failure (1)" in caplog.text


async def test_select_input_source(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    input_sources: Sequence[MediaItem],
) -> None:
    """Tests selecting input source and state."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # Test proper service called
    input_source = input_sources[0]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_INPUT_SOURCE: input_source.name,
        },
        blocking=True,
    )
    player.play_media.assert_called_once_with(input_source)
    # Test state is matched by media id
    player.now_playing_media.source_id = const.MUSIC_SOURCE_AUX_INPUT
    player.now_playing_media.media_id = const.INPUT_AUX_IN_1
    player.now_playing_media.station = input_source.name
    player.heos.dispatcher.send(
        SignalType.PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_INPUT_SOURCE] == input_source.name


@pytest.mark.usefixtures("controller")
async def test_select_input_unknown(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests selecting an unknown input."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_INPUT_SOURCE: "Unknown"},
        blocking=True,
    )
    assert "Unknown source: Unknown" in caplog.text


async def test_select_input_command_error(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
    input_sources: Sequence[MediaItem],
) -> None:
    """Tests selecting an unknown input."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    input_source = input_sources[0]
    player.play_media.side_effect = CommandFailedError(None, "Failure", 1)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_INPUT_SOURCE: input_source.name,
        },
        blocking=True,
    )
    player.play_media.assert_called_once_with(input_source)
    assert "Unable to select source: Failure (1)" in caplog.text


@pytest.mark.usefixtures("controller")
async def test_unload_config_entry(
    hass: HomeAssistant, config_entry: MockHeosConfigEntry
) -> None:
    """Test the player is set unavailable when the config entry is unloaded."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert hass.states.get("media_player.test_player").state == STATE_UNAVAILABLE


async def test_play_media_url(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the play media service with type url."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    url = "http://news/podcast.mp3"
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: MediaType.URL,
                ATTR_MEDIA_CONTENT_ID: url,
            },
            blocking=True,
        )
        player.play_url.assert_called_once_with(url)
        player.play_url.reset_mock()
        player.play_url.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to play media: Failure (1)" in caplog.text


async def test_play_media_music(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the play media service with type music."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    url = "http://news/podcast.mp3"
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: url,
            },
            blocking=True,
        )
        player.play_url.assert_called_once_with(url)
        player.play_url.reset_mock()
        player.play_url.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to play media: Failure (1)" in caplog.text


async def test_play_media_quick_select(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
    quick_selects: dict[int, str],
) -> None:
    """Test the play media service with type quick_select."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    quick_select = list(quick_selects.items())[0]
    index = quick_select[0]
    name = quick_select[1]
    # Play by index
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "quick_select",
            ATTR_MEDIA_CONTENT_ID: str(index),
        },
        blocking=True,
    )
    player.play_quick_select.assert_called_once_with(index)
    # Play by name
    player.play_quick_select.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "quick_select",
            ATTR_MEDIA_CONTENT_ID: name,
        },
        blocking=True,
    )
    player.play_quick_select.assert_called_once_with(index)
    # Invalid name
    player.play_quick_select.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "quick_select",
            ATTR_MEDIA_CONTENT_ID: "Invalid",
        },
        blocking=True,
    )
    assert player.play_quick_select.call_count == 0
    assert "Unable to play media: Invalid quick select 'Invalid'" in caplog.text


async def test_play_media_playlist(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
    playlists: Sequence[MediaItem],
) -> None:
    """Test the play media service with type playlist."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    playlist = playlists[0]
    # Play without enqueuing
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
            ATTR_MEDIA_CONTENT_ID: playlist.name,
        },
        blocking=True,
    )
    player.add_to_queue.assert_called_once_with(
        playlist, AddCriteriaType.REPLACE_AND_PLAY
    )
    # Play with enqueuing
    player.add_to_queue.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
            ATTR_MEDIA_CONTENT_ID: playlist.name,
            ATTR_MEDIA_ENQUEUE: True,
        },
        blocking=True,
    )
    player.add_to_queue.assert_called_once_with(playlist, AddCriteriaType.ADD_TO_END)
    # Invalid name
    player.add_to_queue.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
            ATTR_MEDIA_CONTENT_ID: "Invalid",
        },
        blocking=True,
    )
    assert player.add_to_queue.call_count == 0
    assert "Unable to play media: Invalid playlist 'Invalid'" in caplog.text


async def test_play_media_favorite(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
    favorites: dict[int, MediaItem],
) -> None:
    """Test the play media service with type favorite."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    quick_select = list(favorites.items())[0]
    index = quick_select[0]
    name = quick_select[1].name
    # Play by index
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "favorite",
            ATTR_MEDIA_CONTENT_ID: str(index),
        },
        blocking=True,
    )
    player.play_preset_station.assert_called_once_with(index)
    # Play by name
    player.play_preset_station.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "favorite",
            ATTR_MEDIA_CONTENT_ID: name,
        },
        blocking=True,
    )
    player.play_preset_station.assert_called_once_with(index)
    # Invalid name
    player.play_preset_station.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "favorite",
            ATTR_MEDIA_CONTENT_ID: "Invalid",
        },
        blocking=True,
    )
    assert player.play_preset_station.call_count == 0
    assert "Unable to play media: Invalid favorite 'Invalid'" in caplog.text


@pytest.mark.usefixtures("controller")
async def test_play_media_invalid_type(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the play media service with an invalid type."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "Other",
            ATTR_MEDIA_CONTENT_ID: "",
        },
        blocking=True,
    )
    assert "Unable to play media: Unsupported media type 'Other'" in caplog.text


@pytest.mark.parametrize(
    ("members", "expected"),
    [
        (["media_player.test_player_2"], (1, [2])),
        (["media_player.test_player_2", "media_player.test_player"], (1, [2])),
        (["media_player.test_player"], (1, [])),
    ],
)
async def test_media_player_join_group(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    members: list[str],
    expected: tuple[int, list[int]],
) -> None:
    """Test grouping of media players through the join service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_GROUP_MEMBERS: members,
        },
        blocking=True,
    )
    controller.set_group.assert_called_once_with(*expected)


async def test_media_player_join_group_error(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test grouping of media players errors, does not join."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.set_group.side_effect = HeosError("error")
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_GROUP_MEMBERS: ["media_player.test_player_2"],
        },
        blocking=True,
    )
    assert "Unable to join players" in caplog.text


async def test_media_player_group_members(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test group_members attribute."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    player_entity = hass.states.get("media_player.test_player")
    assert player_entity.attributes[ATTR_GROUP_MEMBERS] == [
        "media_player.test_player",
        "media_player.test_player_2",
    ]
    controller.get_groups.assert_called_once()


async def test_media_player_group_members_error(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
) -> None:
    """Test error in HEOS API."""
    controller.get_groups.side_effect = HeosError("error")
    controller._groups = {}
    for player in controller.players.values():
        player.group_id = None
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player_entity = hass.states.get("media_player.test_player")
    assert player_entity.attributes[ATTR_GROUP_MEMBERS] is None


@pytest.mark.parametrize(
    ("entity_id", "expected_args"),
    [("media_player.test_player", [1]), ("media_player.test_player_2", [1])],
)
async def test_media_player_unjoin_group(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    entity_id: str,
    expected_args: list[int],
) -> None:
    """Test ungrouping of media players through the unjoin service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_UNJOIN,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    controller.set_group.assert_called_once_with(expected_args)


async def test_media_player_unjoin_group_error(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test ungrouping of media players with error logs."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.set_group.side_effect = HeosError("error")
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_UNJOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
        },
        blocking=True,
    )
    assert "Unable to unjoin player: error" in caplog.text


async def test_media_player_group_fails_when_entity_removed(
    hass: HomeAssistant,
    config_entry: MockHeosConfigEntry,
    controller: Heos,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test grouping fails when entity removed."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    # Remove one of the players
    entity_registry.async_remove("media_player.test_player_2")

    # Attempt to group
    with pytest.raises(
        ServiceValidationError,
        match="Entity media_player.test_player_2 was not found",
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_GROUP_MEMBERS: ["media_player.test_player_2"],
            },
            blocking=True,
        )
    controller.set_group.assert_not_called()
