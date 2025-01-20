"""Tests for the Heos Media Player platform."""

import asyncio
from collections.abc import Sequence
import re
from typing import Any

from pyheos import (
    AddCriteriaType,
    CommandFailedError,
    Heos,
    HeosError,
    MediaItem,
    PlayState,
    SignalHeosEvent,
    SignalType,
    const,
)
import pytest

from homeassistant.components.heos import media_player
from homeassistant.components.heos.const import DOMAIN, SIGNAL_HEOS_UPDATED
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_platform(
    hass: HomeAssistant, config_entry: MockConfigEntry, config: dict[str, Any]
) -> None:
    """Set up the media player platform for testing."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_state_attributes(
    hass: HomeAssistant, config_entry, config, controller
) -> None:
    """Tests the state attributes."""
    await setup_platform(hass, config_entry, config)
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
        | media_player.BASE_SUPPORTED_FEATURES
    )
    assert ATTR_INPUT_SOURCE not in state.attributes
    assert (
        state.attributes[ATTR_INPUT_SOURCE_LIST]
        == config_entry.runtime_data.source_manager.source_list
    )


async def test_updates_from_signals(
    hass: HomeAssistant, config_entry, config, controller, favorites
) -> None:
    """Tests dispatched signals update player."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]

    # Test player does not update for other players
    player.state = PlayState.PLAY
    player.heos.dispatcher.send(
        SignalType.PLAYER_EVENT, 2, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE

    # Test player_update standard events
    player.state = PlayState.PLAY
    player.heos.dispatcher.send(
        SignalType.PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_PLAYING

    # Test player_update progress events
    player.now_playing_media.duration = 360000
    player.now_playing_media.current_position = 1000
    player.heos.dispatcher.send(
        SignalType.PLAYER_EVENT,
        player.player_id,
        const.EVENT_PLAYER_NOW_PLAYING_PROGRESS,
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] is not None
    assert state.attributes[ATTR_MEDIA_DURATION] == 360
    assert state.attributes[ATTR_MEDIA_POSITION] == 1


async def test_updates_from_connection_event(
    hass: HomeAssistant,
    config_entry,
    config,
    controller,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests player updates from connection event after connection failure."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    event = asyncio.Event()

    async def set_signal():
        event.set()

    async_dispatcher_connect(hass, SIGNAL_HEOS_UPDATED, set_signal)

    # Connected
    player.available = True
    player.heos.dispatcher.send(SignalType.HEOS_EVENT, SignalHeosEvent.CONNECTED)
    await event.wait()
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE
    assert controller.load_players.call_count == 1

    # Disconnected
    event.clear()
    controller.load_players.reset_mock()
    player.available = False
    player.heos.dispatcher.send(SignalType.HEOS_EVENT, SignalHeosEvent.DISCONNECTED)
    await event.wait()
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_UNAVAILABLE
    assert controller.load_players.call_count == 0

    # Connected handles refresh failure
    event.clear()
    controller.load_players.reset_mock()
    controller.load_players.side_effect = CommandFailedError(None, "Failure", 1)
    player.available = True
    player.heos.dispatcher.send(SignalType.HEOS_EVENT, SignalHeosEvent.CONNECTED)
    await event.wait()
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE
    assert controller.load_players.call_count == 1
    assert "Unable to refresh players" in caplog.text


async def test_updates_from_sources_updated(
    hass: HomeAssistant, config_entry, config, controller, input_sources
) -> None:
    """Tests player updates from changes in sources list."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    event = asyncio.Event()

    async def set_signal():
        event.set()

    async_dispatcher_connect(hass, SIGNAL_HEOS_UPDATED, set_signal)

    input_sources.clear()
    player.heos.dispatcher.send(
        SignalType.CONTROLLER_EVENT, const.EVENT_SOURCES_CHANGED, {}
    )
    await event.wait()
    source_list = config_entry.runtime_data.source_manager.source_list
    assert len(source_list) == 2
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == source_list


async def test_updates_from_players_changed(
    hass: HomeAssistant,
    config_entry,
    config,
    controller,
    change_data,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test player updates from changes to available players."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    event = asyncio.Event()

    async def set_signal():
        event.set()

    async_dispatcher_connect(hass, SIGNAL_HEOS_UPDATED, set_signal)

    assert hass.states.get("media_player.test_player").state == STATE_IDLE
    player.state = PlayState.PLAY
    player.heos.dispatcher.send(
        SignalType.CONTROLLER_EVENT, const.EVENT_PLAYERS_CHANGED, change_data
    )
    await event.wait()
    await hass.async_block_till_done()
    assert hass.states.get("media_player.test_player").state == STATE_PLAYING


async def test_updates_from_players_changed_new_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    config_entry,
    config,
    controller,
    change_data_mapped_ids,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test player updates from changes to available players."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    event = asyncio.Event()

    # Assert device registry matches current id
    assert device_registry.async_get_device(identifiers={(DOMAIN, "1")})
    # Assert entity registry matches current id
    assert (
        entity_registry.async_get_entity_id(MEDIA_PLAYER_DOMAIN, DOMAIN, "1")
        == "media_player.test_player"
    )

    # Trigger update
    async def set_signal():
        event.set()

    async_dispatcher_connect(hass, SIGNAL_HEOS_UPDATED, set_signal)
    player.heos.dispatcher.send(
        SignalType.CONTROLLER_EVENT,
        const.EVENT_PLAYERS_CHANGED,
        change_data_mapped_ids,
    )
    await event.wait()

    # Assert device registry identifiers were updated
    assert len(device_registry.devices) == 2
    assert device_registry.async_get_device(identifiers={(DOMAIN, "101")})
    # Assert entity registry unique id was updated
    assert len(entity_registry.entities) == 2
    assert (
        entity_registry.async_get_entity_id(MEDIA_PLAYER_DOMAIN, DOMAIN, "101")
        == "media_player.test_player"
    )


async def test_updates_from_user_changed(
    hass: HomeAssistant, config_entry, config, controller
) -> None:
    """Tests player updates from changes in user."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    event = asyncio.Event()

    async def set_signal():
        event.set()

    async_dispatcher_connect(hass, SIGNAL_HEOS_UPDATED, set_signal)

    controller._signed_in_username = None
    player.heos.dispatcher.send(
        SignalType.CONTROLLER_EVENT, const.EVENT_USER_CHANGED, None
    )
    await event.wait()
    source_list = config_entry.runtime_data.source_manager.source_list
    assert len(source_list) == 1
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == source_list


async def test_clear_playlist(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the clear playlist service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_CLEAR_PLAYLIST,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert player.clear_queue.call_count == 1


async def test_clear_playlist_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test error raised when clear playlist fails."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.clear_queue.side_effect = CommandFailedError(None, "Failure", 1)
    with pytest.raises(
        HomeAssistantError, match=re.escape("Unable to clear playlist: Failure (1)")
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_CLEAR_PLAYLIST,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert player.clear_queue.call_count == 1


async def test_pause(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the pause service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert player.pause.call_count == 1


async def test_pause_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the pause service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.pause.side_effect = CommandFailedError(None, "Failure", 1)
    with pytest.raises(
        HomeAssistantError, match=re.escape("Unable to pause: Failure (1)")
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PAUSE,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert player.pause.call_count == 1


async def test_play(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the play service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert player.play.call_count == 1


async def test_play_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the play service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.play.side_effect = CommandFailedError(None, "Failure", 1)
    with pytest.raises(
        HomeAssistantError, match=re.escape("Unable to play: Failure (1)")
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PLAY,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert player.play.call_count == 1


async def test_previous_track(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the previous track service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert player.play_previous.call_count == 1


async def test_previous_track_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the previous track service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.play_previous.side_effect = CommandFailedError(None, "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to move to previous track: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert player.play_previous.call_count == 1


async def test_next_track(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the next track service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert player.play_next.call_count == 1


async def test_next_track_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the next track service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.play_next.side_effect = CommandFailedError(None, "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to move to next track: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert player.play_next.call_count == 1


async def test_stop(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the stop service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: "media_player.test_player"},
        blocking=True,
    )
    assert player.stop.call_count == 1


async def test_stop_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the stop service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.stop.side_effect = CommandFailedError(None, "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to stop: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_STOP,
            {ATTR_ENTITY_ID: "media_player.test_player"},
            blocking=True,
        )
    assert player.stop.call_count == 1


async def test_volume_mute(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the volume mute service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    assert player.set_mute.call_count == 1


async def test_volume_mute_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the volume mute service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.set_mute.side_effect = CommandFailedError(None, "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to set mute: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_MUTE,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_MUTED: True},
            blocking=True,
        )
    assert player.set_mute.call_count == 1


async def test_shuffle_set(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the shuffle set service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_SHUFFLE: True},
        blocking=True,
    )
    player.set_play_mode.assert_called_once_with(player.repeat, True)


async def test_shuffle_set_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the shuffle set service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.set_play_mode.side_effect = CommandFailedError(None, "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to set shuffle: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SHUFFLE_SET,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_SHUFFLE: True},
            blocking=True,
        )
    player.set_play_mode.assert_called_once_with(player.repeat, True)


async def test_volume_set(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the volume set service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_LEVEL: 1},
        blocking=True,
    )
    player.set_volume.assert_called_once_with(100)


async def test_volume_set_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the volume set service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.set_volume.side_effect = CommandFailedError(None, "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to set volume level: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_SET,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_MEDIA_VOLUME_LEVEL: 1},
            blocking=True,
        )
    player.set_volume.assert_called_once_with(100)


async def test_select_favorite(
    hass: HomeAssistant, config_entry, config, controller, favorites
) -> None:
    """Tests selecting a music service favorite and state."""
    await setup_platform(hass, config_entry, config)
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
    hass: HomeAssistant, config_entry, config, controller, favorites
) -> None:
    """Tests selecting a radio favorite and state."""
    await setup_platform(hass, config_entry, config)
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
    config_entry: MockConfigEntry,
    controller: Heos,
    favorites: dict[int, MediaItem],
) -> None:
    """Tests command error raises when playing favorite."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    # Test set radio preset
    favorite = favorites[2]
    player.play_preset_station.side_effect = CommandFailedError(None, "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to select source: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_INPUT_SOURCE: favorite.name,
            },
            blocking=True,
        )
    player.play_preset_station.assert_called_once_with(2)


async def test_select_input_source(
    hass: HomeAssistant, config_entry, config, controller, input_sources
) -> None:
    """Tests selecting input source and state."""
    await setup_platform(hass, config_entry, config)
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
    player.play_input_source.assert_called_once_with(input_source.media_id)
    # Test state is matched by media id
    player.now_playing_media.source_id = const.MUSIC_SOURCE_AUX_INPUT
    player.now_playing_media.media_id = const.INPUT_AUX_IN_1
    player.heos.dispatcher.send(
        SignalType.PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_INPUT_SOURCE] == input_source.name


@pytest.mark.usefixtures("controller")
async def test_select_input_unknown_raises(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Tests selecting an unknown input raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    with pytest.raises(
        ServiceValidationError,
        match=re.escape("Unknown source: Unknown"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: "media_player.test_player", ATTR_INPUT_SOURCE: "Unknown"},
            blocking=True,
        )


async def test_select_input_command_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: Heos,
    input_sources: Sequence[MediaItem],
) -> None:
    """Tests selecting an unknown input."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    input_source = input_sources[0]
    player.play_input_source.side_effect = CommandFailedError(None, "Failure", 1)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to select source: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_INPUT_SOURCE: input_source.name,
            },
            blocking=True,
        )
    player.play_input_source.assert_called_once_with(input_source.media_id)


async def test_unload_config_entry(
    hass: HomeAssistant, config_entry, config, controller
) -> None:
    """Test the player is set unavailable when the config entry is unloaded."""
    await setup_platform(hass, config_entry, config)
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert hass.states.get("media_player.test_player").state == STATE_UNAVAILABLE


@pytest.mark.parametrize("media_type", [MediaType.URL, MediaType.MUSIC])
async def test_play_media(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: Heos,
    media_type: MediaType,
) -> None:
    """Test the play media service with type url."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    url = "http://news/podcast.mp3"
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: url,
        },
        blocking=True,
    )
    player.play_url.assert_called_once_with(url)


@pytest.mark.parametrize("media_type", [MediaType.URL, MediaType.MUSIC])
async def test_play_media_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: Heos,
    media_type: MediaType,
) -> None:
    """Test the play media service with type url error raises."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    player.play_url.side_effect = CommandFailedError(None, "Failure", 1)
    url = "http://news/podcast.mp3"
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to play media: Failure (1)"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: media_type,
                ATTR_MEDIA_CONTENT_ID: url,
            },
            blocking=True,
        )
    player.play_url.assert_called_once_with(url)


@pytest.mark.parametrize(
    ("content_id", "expected_index"), [("1", 1), ("Quick Select 2", 2)]
)
async def test_play_media_quick_select(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: Heos,
    content_id: str,
    expected_index: int,
) -> None:
    """Test the play media service with type quick_select."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "quick_select",
            ATTR_MEDIA_CONTENT_ID: content_id,
        },
        blocking=True,
    )
    player.play_quick_select.assert_called_once_with(expected_index)


async def test_play_media_quick_select_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the play media service with invalid quick_select raises."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to play media: Invalid quick select 'Invalid'"),
    ):
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


@pytest.mark.parametrize(
    ("enqueue", "criteria"),
    [
        (None, AddCriteriaType.REPLACE_AND_PLAY),
        (True, AddCriteriaType.ADD_TO_END),
        ("next", AddCriteriaType.PLAY_NEXT),
    ],
)
async def test_play_media_playlist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: Heos,
    playlists: Sequence[MediaItem],
    enqueue: Any,
    criteria: AddCriteriaType,
) -> None:
    """Test the play media service with type playlist."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    playlist = playlists[0]
    service_data = {
        ATTR_ENTITY_ID: "media_player.test_player",
        ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
        ATTR_MEDIA_CONTENT_ID: playlist.name,
    }
    if enqueue is not None:
        service_data[ATTR_MEDIA_ENQUEUE] = enqueue
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        service_data,
        blocking=True,
    )
    player.add_to_queue.assert_called_once_with(playlist, criteria)


async def test_play_media_playlist_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the play media service with an invalid playlist name."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to play media: Invalid playlist 'Invalid'"),
    ):
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


@pytest.mark.parametrize(
    ("content_id", "expected_index"), [("1", 1), ("Classical MPR (Classical Music)", 2)]
)
async def test_play_media_favorite(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: Heos,
    content_id: str,
    expected_index: int,
) -> None:
    """Test the play media service with type favorite."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: "favorite",
            ATTR_MEDIA_CONTENT_ID: content_id,
        },
        blocking=True,
    )
    player.play_preset_station.assert_called_once_with(expected_index)


async def test_play_media_favorite_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test the play media service with an invalid favorite raises."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    player = controller.players[1]
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to play media: Invalid favorite 'Invalid'"),
    ):
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


@pytest.mark.usefixtures("controller")
async def test_play_media_invalid_type(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the play media service with an invalid type."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to play media: Unsupported media type 'Other'"),
    ):
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


async def test_media_player_join_group(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test grouping of media players through the join service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_JOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_GROUP_MEMBERS: ["media_player.test_player_2"],
        },
        blocking=True,
    )
    controller.create_group.assert_called_once_with(
        1,
        [
            2,
        ],
    )


async def test_media_player_join_group_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test grouping of media players through the join service raises error."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.create_group.side_effect = HeosError("error")
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to join players: error"),
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


async def test_media_player_group_members(
    hass: HomeAssistant,
    config_entry,
    config,
    controller,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test group_members attribute."""
    await setup_platform(hass, config_entry, config)
    await hass.async_block_till_done()
    player_entity = hass.states.get("media_player.test_player")
    assert player_entity.attributes[ATTR_GROUP_MEMBERS] == [
        "media_player.test_player",
        "media_player.test_player_2",
    ]
    controller.get_groups.assert_called_once()
    assert "Unable to get HEOS group info" not in caplog.text


async def test_media_player_group_members_error(
    hass: HomeAssistant,
    config_entry,
    config,
    controller,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error in HEOS API."""
    controller.get_groups.side_effect = HeosError("error")
    await setup_platform(hass, config_entry, config)
    await hass.async_block_till_done()
    assert "Unable to get HEOS group info" in caplog.text
    player_entity = hass.states.get("media_player.test_player")
    assert player_entity.attributes[ATTR_GROUP_MEMBERS] == []


async def test_media_player_unjoin_group(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test ungrouping of media players through the unjoin service."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_UNJOIN,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
        },
        blocking=True,
    )
    controller.create_group.assert_called_once_with(1, [])


async def test_media_player_unjoin_group_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: Heos
) -> None:
    """Test ungrouping of media players through the unjoin service error raises."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    controller.create_group.side_effect = HeosError("error")
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Unable to unjoin player: error"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_UNJOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
            },
            blocking=True,
        )


async def test_media_player_group_fails_when_entity_removed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
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
        HomeAssistantError,
        match="The group member media_player.test_player_2 could not be resolved to a HEOS player.",
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
    controller.create_group.assert_not_called()
