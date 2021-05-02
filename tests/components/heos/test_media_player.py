"""Tests for the Heos Media Player platform."""
import asyncio
from unittest.mock import patch

from pyheos import CommandFailedError, const
from pyheos.error import HeosError

from homeassistant.components.heos import media_player
from homeassistant.components.heos.const import (
    DATA_GROUP_MANAGER,
    DATA_SOURCE_MANAGER,
    DOMAIN,
    SIGNAL_HEOS_UPDATED,
)
from homeassistant.components.media_player.const import (
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
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_URL,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_JOIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SERVICE_UNJOIN,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP,
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
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component


async def setup_platform(hass, config_entry, config):
    """Set up the media player platform for testing."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_state_attributes(hass, config_entry, config, controller):
    """Tests the state attributes."""
    await setup_platform(hass, config_entry, config)
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.25
    assert not state.attributes[ATTR_MEDIA_VOLUME_MUTED]
    assert state.attributes[ATTR_MEDIA_CONTENT_ID] == "1"
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_MUSIC
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
        == SUPPORT_PLAY
        | SUPPORT_PAUSE
        | SUPPORT_STOP
        | SUPPORT_NEXT_TRACK
        | SUPPORT_PREVIOUS_TRACK
        | media_player.BASE_SUPPORTED_FEATURES
    )
    assert ATTR_INPUT_SOURCE not in state.attributes
    assert (
        state.attributes[ATTR_INPUT_SOURCE_LIST]
        == hass.data[DOMAIN][DATA_SOURCE_MANAGER].source_list
    )


async def test_updates_from_signals(hass, config_entry, config, controller, favorites):
    """Tests dispatched signals update player."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]

    # Test player does not update for other players
    player.state = const.PLAY_STATE_PLAY
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT, 2, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE

    # Test player_update standard events
    player.state = const.PLAY_STATE_PLAY
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_PLAYING

    # Test player_update progress events
    player.now_playing_media.duration = 360000
    player.now_playing_media.current_position = 1000
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT,
        player.player_id,
        const.EVENT_PLAYER_NOW_PLAYING_PROGRESS,
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] is not None
    assert state.attributes[ATTR_MEDIA_DURATION] == 360
    assert state.attributes[ATTR_MEDIA_POSITION] == 1


async def test_updates_from_connection_event(
    hass, config_entry, config, controller, caplog
):
    """Tests player updates from connection event after connection failure."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    event = asyncio.Event()

    async def set_signal():
        event.set()

    hass.helpers.dispatcher.async_dispatcher_connect(SIGNAL_HEOS_UPDATED, set_signal)

    # Connected
    player.available = True
    player.heos.dispatcher.send(const.SIGNAL_HEOS_EVENT, const.EVENT_CONNECTED)
    await event.wait()
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE
    assert controller.load_players.call_count == 1

    # Disconnected
    event.clear()
    player.reset_mock()
    controller.load_players.reset_mock()
    player.available = False
    player.heos.dispatcher.send(const.SIGNAL_HEOS_EVENT, const.EVENT_DISCONNECTED)
    await event.wait()
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_UNAVAILABLE
    assert controller.load_players.call_count == 0

    # Connected handles refresh failure
    event.clear()
    player.reset_mock()
    controller.load_players.reset_mock()
    controller.load_players.side_effect = CommandFailedError(None, "Failure", 1)
    player.available = True
    player.heos.dispatcher.send(const.SIGNAL_HEOS_EVENT, const.EVENT_CONNECTED)
    await event.wait()
    state = hass.states.get("media_player.test_player")
    assert state.state == STATE_IDLE
    assert controller.load_players.call_count == 1
    assert "Unable to refresh players" in caplog.text


async def test_updates_from_sources_updated(
    hass, config_entry, config, controller, input_sources
):
    """Tests player updates from changes in sources list."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    event = asyncio.Event()

    async def set_signal():
        event.set()

    hass.helpers.dispatcher.async_dispatcher_connect(SIGNAL_HEOS_UPDATED, set_signal)

    input_sources.clear()
    player.heos.dispatcher.send(
        const.SIGNAL_CONTROLLER_EVENT, const.EVENT_SOURCES_CHANGED, {}
    )
    await event.wait()
    source_list = hass.data[DOMAIN][DATA_SOURCE_MANAGER].source_list
    assert len(source_list) == 2
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == source_list


async def test_updates_from_players_changed(
    hass, config_entry, config, controller, change_data, caplog
):
    """Test player updates from changes to available players."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    event = asyncio.Event()

    async def set_signal():
        event.set()

    hass.helpers.dispatcher.async_dispatcher_connect(SIGNAL_HEOS_UPDATED, set_signal)

    assert hass.states.get("media_player.test_player").state == STATE_IDLE
    player.state = const.PLAY_STATE_PLAY
    player.heos.dispatcher.send(
        const.SIGNAL_CONTROLLER_EVENT, const.EVENT_PLAYERS_CHANGED, change_data
    )
    await event.wait()
    await hass.async_block_till_done()
    assert hass.states.get("media_player.test_player").state == STATE_PLAYING


async def test_updates_from_players_changed_new_ids(
    hass, config_entry, config, controller, change_data_mapped_ids, caplog
):
    """Test player updates from changes to available players."""
    await setup_platform(hass, config_entry, config)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    player = controller.players[1]
    event = asyncio.Event()

    # Assert device registry matches current id
    assert device_registry.async_get_device({(DOMAIN, 1)})
    # Assert entity registry matches current id
    assert (
        entity_registry.async_get_entity_id(MEDIA_PLAYER_DOMAIN, DOMAIN, "1")
        == "media_player.test_player"
    )

    # Trigger update
    async def set_signal():
        event.set()

    hass.helpers.dispatcher.async_dispatcher_connect(SIGNAL_HEOS_UPDATED, set_signal)
    player.heos.dispatcher.send(
        const.SIGNAL_CONTROLLER_EVENT,
        const.EVENT_PLAYERS_CHANGED,
        change_data_mapped_ids,
    )
    await event.wait()

    # Assert device registry identifiers were updated
    assert len(device_registry.devices) == 2
    assert device_registry.async_get_device({(DOMAIN, 101)})
    # Assert entity registry unique id was updated
    assert len(entity_registry.entities) == 2
    assert (
        entity_registry.async_get_entity_id(MEDIA_PLAYER_DOMAIN, DOMAIN, "101")
        == "media_player.test_player"
    )


async def test_updates_from_user_changed(hass, config_entry, config, controller):
    """Tests player updates from changes in user."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    event = asyncio.Event()

    async def set_signal():
        event.set()

    hass.helpers.dispatcher.async_dispatcher_connect(SIGNAL_HEOS_UPDATED, set_signal)

    controller.is_signed_in = False
    controller.signed_in_username = None
    player.heos.dispatcher.send(
        const.SIGNAL_CONTROLLER_EVENT, const.EVENT_USER_CHANGED, None
    )
    await event.wait()
    source_list = hass.data[DOMAIN][DATA_SOURCE_MANAGER].source_list
    assert len(source_list) == 1
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == source_list


async def test_clear_playlist(hass, config_entry, config, controller, caplog):
    """Test the clear playlist service."""
    await setup_platform(hass, config_entry, config)
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


async def test_pause(hass, config_entry, config, controller, caplog):
    """Test the pause service."""
    await setup_platform(hass, config_entry, config)
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


async def test_play(hass, config_entry, config, controller, caplog):
    """Test the play service."""
    await setup_platform(hass, config_entry, config)
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


async def test_previous_track(hass, config_entry, config, controller, caplog):
    """Test the previous track service."""
    await setup_platform(hass, config_entry, config)
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


async def test_next_track(hass, config_entry, config, controller, caplog):
    """Test the next track service."""
    await setup_platform(hass, config_entry, config)
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


async def test_stop(hass, config_entry, config, controller, caplog):
    """Test the stop service."""
    await setup_platform(hass, config_entry, config)
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


async def test_volume_mute(hass, config_entry, config, controller, caplog):
    """Test the volume mute service."""
    await setup_platform(hass, config_entry, config)
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


async def test_shuffle_set(hass, config_entry, config, controller, caplog):
    """Test the shuffle set service."""
    await setup_platform(hass, config_entry, config)
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


async def test_volume_set(hass, config_entry, config, controller, caplog):
    """Test the volume set service."""
    await setup_platform(hass, config_entry, config)
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


async def test_select_favorite(hass, config_entry, config, controller, favorites):
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
    player.play_favorite.assert_called_once_with(1)
    # Test state is matched by station name
    player.now_playing_media.station = favorite.name
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_INPUT_SOURCE] == favorite.name


async def test_select_radio_favorite(hass, config_entry, config, controller, favorites):
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
    player.play_favorite.assert_called_once_with(2)
    # Test state is matched by album id
    player.now_playing_media.station = "Classical"
    player.now_playing_media.album_id = favorite.media_id
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_INPUT_SOURCE] == favorite.name


async def test_select_radio_favorite_command_error(
    hass, config_entry, config, controller, favorites, caplog
):
    """Tests command error logged when playing favorite."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    # Test set radio preset
    favorite = favorites[2]
    player.play_favorite.side_effect = CommandFailedError(None, "Failure", 1)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_INPUT_SOURCE: favorite.name},
        blocking=True,
    )
    player.play_favorite.assert_called_once_with(2)
    assert "Unable to select source: Failure (1)" in caplog.text


async def test_select_input_source(
    hass, config_entry, config, controller, input_sources
):
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
    player.play_input_source.assert_called_once_with(input_source)
    # Test state is matched by media id
    player.now_playing_media.source_id = const.MUSIC_SOURCE_AUX_INPUT
    player.now_playing_media.media_id = const.INPUT_AUX_IN_1
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT, player.player_id, const.EVENT_PLAYER_STATE_CHANGED
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_player")
    assert state.attributes[ATTR_INPUT_SOURCE] == input_source.name


async def test_select_input_unknown(hass, config_entry, config, controller, caplog):
    """Tests selecting an unknown input."""
    await setup_platform(hass, config_entry, config)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.test_player", ATTR_INPUT_SOURCE: "Unknown"},
        blocking=True,
    )
    assert "Unknown source: Unknown" in caplog.text


async def test_select_input_command_error(
    hass, config_entry, config, controller, caplog, input_sources
):
    """Tests selecting an unknown input."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    input_source = input_sources[0]
    player.play_input_source.side_effect = CommandFailedError(None, "Failure", 1)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_INPUT_SOURCE: input_source.name,
        },
        blocking=True,
    )
    player.play_input_source.assert_called_once_with(input_source)
    assert "Unable to select source: Failure (1)" in caplog.text


async def test_unload_config_entry(hass, config_entry, config, controller):
    """Test the player is set unavailable when the config entry is unloaded."""
    await setup_platform(hass, config_entry, config)
    await config_entry.async_unload(hass)
    assert hass.states.get("media_player.test_player").state == STATE_UNAVAILABLE


async def test_play_media_url(hass, config_entry, config, controller, caplog):
    """Test the play media service with type url."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    url = "http://news/podcast.mp3"
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_URL,
                ATTR_MEDIA_CONTENT_ID: url,
            },
            blocking=True,
        )
        player.play_url.assert_called_once_with(url)
        player.play_url.reset_mock()
        player.play_url.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to play media: Failure (1)" in caplog.text


async def test_play_media_music(hass, config_entry, config, controller, caplog):
    """Test the play media service with type music."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    url = "http://news/podcast.mp3"
    # First pass completes successfully, second pass raises command error
    for _ in range(2):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_MUSIC,
                ATTR_MEDIA_CONTENT_ID: url,
            },
            blocking=True,
        )
        player.play_url.assert_called_once_with(url)
        player.play_url.reset_mock()
        player.play_url.side_effect = CommandFailedError(None, "Failure", 1)
    assert "Unable to play media: Failure (1)" in caplog.text


async def test_play_media_quick_select(
    hass, config_entry, config, controller, caplog, quick_selects
):
    """Test the play media service with type quick_select."""
    await setup_platform(hass, config_entry, config)
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
    hass, config_entry, config, controller, caplog, playlists
):
    """Test the play media service with type playlist."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    playlist = playlists[0]
    # Play without enqueuing
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_PLAYLIST,
            ATTR_MEDIA_CONTENT_ID: playlist.name,
        },
        blocking=True,
    )
    player.add_to_queue.assert_called_once_with(
        playlist, const.ADD_QUEUE_REPLACE_AND_PLAY
    )
    # Play with enqueuing
    player.add_to_queue.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_PLAYLIST,
            ATTR_MEDIA_CONTENT_ID: playlist.name,
            ATTR_MEDIA_ENQUEUE: True,
        },
        blocking=True,
    )
    player.add_to_queue.assert_called_once_with(playlist, const.ADD_QUEUE_ADD_TO_END)
    # Invalid name
    player.add_to_queue.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_PLAYLIST,
            ATTR_MEDIA_CONTENT_ID: "Invalid",
        },
        blocking=True,
    )
    assert player.add_to_queue.call_count == 0
    assert "Unable to play media: Invalid playlist 'Invalid'" in caplog.text


async def test_play_media_favorite(
    hass, config_entry, config, controller, caplog, favorites
):
    """Test the play media service with type favorite."""
    await setup_platform(hass, config_entry, config)
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
    player.play_favorite.assert_called_once_with(index)
    # Play by name
    player.play_favorite.reset_mock()
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
    player.play_favorite.assert_called_once_with(index)
    # Invalid name
    player.play_favorite.reset_mock()
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
    assert player.play_favorite.call_count == 0
    assert "Unable to play media: Invalid favorite 'Invalid'" in caplog.text


async def test_play_media_invalid_type(hass, config_entry, config, controller, caplog):
    """Test the play media service with an invalid type."""
    await setup_platform(hass, config_entry, config)
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


async def test_media_player_join_group(hass, config_entry, config, controller, caplog):
    """Test grouping of media players through the join service."""
    await setup_platform(hass, config_entry, config)
    with patch.object(controller, "create_group") as mock_create_group:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_GROUP_MEMBERS: ["media_player.test_player_2"],
            },
            blocking=True,
        )
    mock_create_group.assert_called_once_with(
        1,
        [
            2,
        ],
    )
    assert "Failed to group media_player.test_player with" not in caplog.text

    with patch.object(controller, "create_group", side_effect=HeosError("error")):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_JOIN,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_GROUP_MEMBERS: ["media_player.test_player_2"],
            },
            blocking=True,
        )
    assert "Failed to group media_player.test_player with" in caplog.text


async def test_media_player_group_members(
    hass, config_entry, config, controller, group, caplog
):
    """Test group_members attribute."""
    await setup_platform(hass, config_entry, config)
    with patch.object(controller, "get_groups", return_value=group) as mock_get_groups:
        hass.data[DOMAIN][DATA_GROUP_MANAGER].force_update_groups()
        await hass.async_block_till_done()
        player_entity = hass.states.get("media_player.test_player")
        assert player_entity.attributes[ATTR_GROUP_MEMBERS] == [
            "media_player.test_player",
            "media_player.test_player_2",
        ]
    mock_get_groups.assert_called_once()
    assert "Unable to get HEOS group info" not in caplog.text

    with patch.object(
        controller, "get_groups", return_value=group, side_effect=HeosError("error")
    ):
        hass.data[DOMAIN][DATA_GROUP_MANAGER].force_update_groups()
        await hass.async_block_till_done()
    assert "Unable to get HEOS group info" in caplog.text


async def test_media_player_unjoin_group(
    hass, config_entry, config, controller, group, caplog
):
    """Test ungrouping of media players through the join service."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]

    with patch.object(controller, "get_groups", return_value=group):
        player.heos.dispatcher.send(
            const.SIGNAL_PLAYER_EVENT,
            player.player_id,
            const.EVENT_PLAYER_STATE_CHANGED,
        )
        await hass.async_block_till_done()
        with patch.object(controller, "create_group") as mock_create_group:
            await hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_UNJOIN,
                {
                    ATTR_ENTITY_ID: "media_player.test_player",
                },
                blocking=True,
            )
        mock_create_group.assert_called_once_with(1, [])
        assert "Failed to ungroup media_player.test_player" not in caplog.text

        with patch.object(controller, "create_group", side_effect=HeosError("error")):
            await hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_UNJOIN,
                {
                    ATTR_ENTITY_ID: "media_player.test_player",
                },
                blocking=True,
            )
        assert "Failed to ungroup media_player.test_player" in caplog.text
