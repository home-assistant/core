"""Test different accessory types: Media Players."""

from homeassistant.components.homekit.const import (
    CONF_FEATURE_LIST, FEATURE_ON_OFF, FEATURE_PLAY_PAUSE, FEATURE_PLAY_STOP,
    FEATURE_TOGGLE_MUTE)
from homeassistant.components.homekit.type_media_players import MediaPlayer
from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_MUTED, DOMAIN)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, STATE_IDLE, STATE_OFF, STATE_ON,
    STATE_PAUSED, STATE_PLAYING)

from tests.common import async_mock_service


async def test_media_player_set_state(hass, hk_driver):
    """Test if accessory and HA are updated accordingly."""
    config = {CONF_FEATURE_LIST: {
        FEATURE_ON_OFF: None, FEATURE_PLAY_PAUSE: None,
        FEATURE_PLAY_STOP: None, FEATURE_TOGGLE_MUTE: None}}
    entity_id = 'media_player.test'

    hass.states.async_set(entity_id, None, {ATTR_SUPPORTED_FEATURES: 20873,
                                            ATTR_MEDIA_VOLUME_MUTED: False})
    await hass.async_block_till_done()
    acc = MediaPlayer(hass, hk_driver, 'MediaPlayer', entity_id, 2, config)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 8  # Switch

    assert acc.chars[FEATURE_ON_OFF].value == 0
    assert acc.chars[FEATURE_PLAY_PAUSE].value == 0
    assert acc.chars[FEATURE_PLAY_STOP].value == 0
    assert acc.chars[FEATURE_TOGGLE_MUTE].value == 0

    hass.states.async_set(entity_id, STATE_ON, {ATTR_MEDIA_VOLUME_MUTED: True})
    await hass.async_block_till_done()
    assert acc.chars[FEATURE_ON_OFF].value == 1
    assert acc.chars[FEATURE_TOGGLE_MUTE].value == 1

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert acc.chars[FEATURE_ON_OFF].value == 0

    hass.states.async_set(entity_id, STATE_PLAYING)
    await hass.async_block_till_done()
    assert acc.chars[FEATURE_PLAY_PAUSE].value == 1
    assert acc.chars[FEATURE_PLAY_STOP].value == 1

    hass.states.async_set(entity_id, STATE_PAUSED)
    await hass.async_block_till_done()
    assert acc.chars[FEATURE_PLAY_PAUSE].value == 0

    hass.states.async_set(entity_id, STATE_IDLE)
    await hass.async_block_till_done()
    assert acc.chars[FEATURE_PLAY_STOP].value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, 'turn_on')
    call_turn_off = async_mock_service(hass, DOMAIN, 'turn_off')
    call_media_play = async_mock_service(hass, DOMAIN, 'media_play')
    call_media_pause = async_mock_service(hass, DOMAIN, 'media_pause')
    call_media_stop = async_mock_service(hass, DOMAIN, 'media_stop')
    call_toggle_mute = async_mock_service(hass, DOMAIN, 'volume_mute')

    await hass.async_add_job(acc.chars[FEATURE_ON_OFF]
                             .client_update_value, True)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id

    await hass.async_add_job(acc.chars[FEATURE_ON_OFF]
                             .client_update_value, False)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id

    await hass.async_add_job(acc.chars[FEATURE_PLAY_PAUSE]
                             .client_update_value, True)
    await hass.async_block_till_done()
    assert call_media_play
    assert call_media_play[0].data[ATTR_ENTITY_ID] == entity_id

    await hass.async_add_job(acc.chars[FEATURE_PLAY_PAUSE]
                             .client_update_value, False)
    await hass.async_block_till_done()
    assert call_media_pause
    assert call_media_pause[0].data[ATTR_ENTITY_ID] == entity_id

    await hass.async_add_job(acc.chars[FEATURE_PLAY_STOP]
                             .client_update_value, True)
    await hass.async_block_till_done()
    assert call_media_play
    assert call_media_play[1].data[ATTR_ENTITY_ID] == entity_id

    await hass.async_add_job(acc.chars[FEATURE_PLAY_STOP]
                             .client_update_value, False)
    await hass.async_block_till_done()
    assert call_media_stop
    assert call_media_stop[0].data[ATTR_ENTITY_ID] == entity_id

    await hass.async_add_job(acc.chars[FEATURE_TOGGLE_MUTE]
                             .client_update_value, True)
    await hass.async_block_till_done()
    assert call_toggle_mute
    assert call_toggle_mute[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_toggle_mute[0].data[ATTR_MEDIA_VOLUME_MUTED] is True

    await hass.async_add_job(acc.chars[FEATURE_TOGGLE_MUTE]
                             .client_update_value, False)
    await hass.async_block_till_done()
    assert call_toggle_mute
    assert call_toggle_mute[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_toggle_mute[1].data[ATTR_MEDIA_VOLUME_MUTED] is False
