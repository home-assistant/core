"""Tests for the Heos Media Player platform."""
from pyheos import const

from homeassistant.components.heos import media_player
from homeassistant.components.heos.const import DOMAIN
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ALBUM_NAME, ATTR_MEDIA_ARTIST, ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE, ATTR_MEDIA_DURATION, ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT, ATTR_MEDIA_SHUFFLE, ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL, ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN, MEDIA_TYPE_MUSIC, SERVICE_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP)
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


async def test_updates_start_from_signals(
        hass, config_entry, config, controller):
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


async def test_unload_config_entry(hass, config_entry, config, controller):
    """Test the player is removed when the config entry is unloaded."""
    await setup_platform(hass, config_entry, config)
    await config_entry.async_unload(hass)
    assert not hass.states.get('media_player.test_player')
