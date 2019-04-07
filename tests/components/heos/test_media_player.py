"""Tests for the Heos Media Player platform."""
import asyncio

from pyheos import const

from homeassistant.components.heos import media_player
from homeassistant.components.heos.const import (
    DATA_SOURCE_MANAGER, DOMAIN, SIGNAL_HEOS_SOURCES_UPDATED)
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE, ATTR_INPUT_SOURCE_LIST, ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST, ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION, ATTR_MEDIA_POSITION, ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_SHUFFLE, ATTR_MEDIA_TITLE, ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED, DOMAIN as MEDIA_PLAYER_DOMAIN, MEDIA_TYPE_MUSIC,
    SERVICE_CLEAR_PLAYLIST, SERVICE_SELECT_SOURCE, SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK, SUPPORT_STOP)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK, SERVICE_MEDIA_STOP, SERVICE_SHUFFLE_SET,
    SERVICE_VOLUME_MUTE, SERVICE_VOLUME_SET, STATE_IDLE, STATE_PLAYING,
    STATE_UNAVAILABLE)
from homeassistant.setup import async_setup_component


async def setup_platform(hass, config_entry, config):
    """Set up the media player platform for testing."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_async_setup_platform():
    """Test setup platform does nothing (it uses config entries)."""
    await media_player.async_setup_platform(None, None, None)


async def test_state_attributes(hass, config_entry, config, controller):
    """Tests the state attributes."""
    await setup_platform(hass, config_entry, config)
    state = hass.states.get('media_player.test_player')
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
    assert state.attributes['media_album_id'] == 1
    assert state.attributes['media_queue_id'] == 1
    assert state.attributes['media_source_id'] == 1
    assert state.attributes['media_station'] == "Station Name"
    assert state.attributes['media_type'] == "Station"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Test Player"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == \
        SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_STOP | SUPPORT_NEXT_TRACK | \
        SUPPORT_PREVIOUS_TRACK | media_player.BASE_SUPPORTED_FEATURES
    assert ATTR_INPUT_SOURCE not in state.attributes
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == \
        hass.data[DOMAIN][DATA_SOURCE_MANAGER].source_list


async def test_updates_start_from_signals(
        hass, config_entry, config, controller, favorites):
    """Tests dispatched signals update player."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]

    # Test player does not update for other players
    player.state = const.PLAY_STATE_PLAY
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT, 2,
        const.EVENT_PLAYER_STATE_CHANGED)
    await hass.async_block_till_done()
    state = hass.states.get('media_player.test_player')
    assert state.state == STATE_IDLE

    # Test player_update standard events
    player.state = const.PLAY_STATE_PLAY
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT, player.player_id,
        const.EVENT_PLAYER_STATE_CHANGED)
    await hass.async_block_till_done()
    state = hass.states.get('media_player.test_player')
    assert state.state == STATE_PLAYING

    # Test player_update progress events
    player.now_playing_media.duration = 360000
    player.now_playing_media.current_position = 1000
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT, player.player_id,
        const.EVENT_PLAYER_NOW_PLAYING_PROGRESS)
    await hass.async_block_till_done()
    state = hass.states.get('media_player.test_player')
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] is not None
    assert state.attributes[ATTR_MEDIA_DURATION] == 360
    assert state.attributes[ATTR_MEDIA_POSITION] == 1

    # Test controller player change updates
    player.available = False
    player.heos.dispatcher.send(
        const.SIGNAL_CONTROLLER_EVENT, const.EVENT_PLAYERS_CHANGED)
    await hass.async_block_till_done()
    state = hass.states.get('media_player.test_player')
    assert state.state == STATE_UNAVAILABLE

    # Test heos events update
    player.available = True
    player.heos.dispatcher.send(
        const.SIGNAL_HEOS_EVENT, const.EVENT_CONNECTED)
    await hass.async_block_till_done()
    state = hass.states.get('media_player.test_player')
    assert state.state == STATE_PLAYING

    # Test sources event update
    event = asyncio.Event()

    async def set_signal():
        event.set()
    hass.helpers.dispatcher.async_dispatcher_connect(
        SIGNAL_HEOS_SOURCES_UPDATED, set_signal)

    favorites.clear()
    player.heos.dispatcher.send(
        const.SIGNAL_CONTROLLER_EVENT, const.EVENT_SOURCES_CHANGED)
    await event.wait()
    source_list = hass.data[DOMAIN][DATA_SOURCE_MANAGER].source_list
    assert len(source_list) == 1
    state = hass.states.get('media_player.test_player')
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == source_list


async def test_services(hass, config_entry, config, controller):
    """Tests player commands."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_CLEAR_PLAYLIST,
        {ATTR_ENTITY_ID: 'media_player.test_player'}, blocking=True)
    assert player.clear_queue.call_count == 1

    player.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: 'media_player.test_player'}, blocking=True)
    assert player.pause.call_count == 1

    player.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: 'media_player.test_player'}, blocking=True)
    assert player.play.call_count == 1

    player.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK,
        {ATTR_ENTITY_ID: 'media_player.test_player'}, blocking=True)
    assert player.play_previous.call_count == 1

    player.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_NEXT_TRACK,
        {ATTR_ENTITY_ID: 'media_player.test_player'}, blocking=True)
    assert player.play_next.call_count == 1

    player.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: 'media_player.test_player'}, blocking=True)
    assert player.stop.call_count == 1

    player.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: 'media_player.test_player',
         ATTR_MEDIA_VOLUME_MUTED: True}, blocking=True)
    player.set_mute.assert_called_once_with(True)

    player.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_SHUFFLE_SET,
        {ATTR_ENTITY_ID: 'media_player.test_player',
         ATTR_MEDIA_SHUFFLE: True}, blocking=True)
    player.set_play_mode.assert_called_once_with(player.repeat, True)

    player.reset_mock()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: 'media_player.test_player',
         ATTR_MEDIA_VOLUME_LEVEL: 1}, blocking=True)
    player.set_volume.assert_called_once_with(100)


async def test_select_favorite(
        hass, config_entry, config, controller, favorites):
    """Tests selecting a music service favorite and state."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    # Test set music service preset
    favorite = favorites[1]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: 'media_player.test_player',
         ATTR_INPUT_SOURCE: favorite.name}, blocking=True)
    player.play_favorite.assert_called_once_with(1)
    # Test state is matched by station name
    player.now_playing_media.station = favorite.name
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT, player.player_id,
        const.EVENT_PLAYER_STATE_CHANGED)
    await hass.async_block_till_done()
    state = hass.states.get('media_player.test_player')
    assert state.attributes[ATTR_INPUT_SOURCE] == favorite.name


async def test_select_radio_favorite(
        hass, config_entry, config, controller, favorites):
    """Tests selecting a radio favorite and state."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    # Test set radio preset
    favorite = favorites[2]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: 'media_player.test_player',
         ATTR_INPUT_SOURCE: favorite.name}, blocking=True)
    player.play_favorite.assert_called_once_with(2)
    # Test state is matched by album id
    player.now_playing_media.station = "Classical"
    player.now_playing_media.album_id = favorite.media_id
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT, player.player_id,
        const.EVENT_PLAYER_STATE_CHANGED)
    await hass.async_block_till_done()
    state = hass.states.get('media_player.test_player')
    assert state.attributes[ATTR_INPUT_SOURCE] == favorite.name


async def test_select_input_source(
        hass, config_entry, config, controller, input_sources):
    """Tests selecting input source and state."""
    await setup_platform(hass, config_entry, config)
    player = controller.players[1]
    # Test proper service called
    input_source = input_sources[0]
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: 'media_player.test_player',
         ATTR_INPUT_SOURCE: input_source.name}, blocking=True)
    player.play_input_source.assert_called_once_with(input_source)
    # Test state is matched by media id
    player.now_playing_media.source_id = const.MUSIC_SOURCE_AUX_INPUT
    player.now_playing_media.media_id = const.INPUT_AUX_IN_1
    player.heos.dispatcher.send(
        const.SIGNAL_PLAYER_EVENT, player.player_id,
        const.EVENT_PLAYER_STATE_CHANGED)
    await hass.async_block_till_done()
    state = hass.states.get('media_player.test_player')
    assert state.attributes[ATTR_INPUT_SOURCE] == input_source.name


async def test_select_input_unknown(
        hass, config_entry, config, controller, caplog):
    """Tests selecting an unknown input."""
    await setup_platform(hass, config_entry, config)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: 'media_player.test_player',
         ATTR_INPUT_SOURCE: "Unknown"}, blocking=True)
    assert "Unknown source: Unknown" in caplog.text


async def test_unload_config_entry(hass, config_entry, config, controller):
    """Test the player is removed when the config entry is unloaded."""
    await setup_platform(hass, config_entry, config)
    await config_entry.async_unload(hass)
    assert not hass.states.get('media_player.test_player')
