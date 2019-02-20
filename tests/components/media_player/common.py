"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE, ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE, ATTR_MEDIA_SEEK_POSITION, ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED, DOMAIN, SERVICE_CLEAR_PLAYLIST,
    SERVICE_PLAY_MEDIA, SERVICE_SELECT_SOURCE)
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY, SERVICE_MEDIA_PLAY_PAUSE, SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK, SERVICE_MEDIA_STOP, SERVICE_TOGGLE, SERVICE_TURN_OFF,
    SERVICE_TURN_ON, SERVICE_VOLUME_DOWN, SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET, SERVICE_VOLUME_UP)
from homeassistant.loader import bind_hass


@bind_hass
def turn_on(hass, entity_id=None):
    """Turn on specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
def turn_off(hass, entity_id=None):
    """Turn off specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


@bind_hass
def toggle(hass, entity_id=None):
    """Toggle specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


@bind_hass
def volume_up(hass, entity_id=None):
    """Send the media player the command for volume up."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_VOLUME_UP, data)


@bind_hass
def volume_down(hass, entity_id=None):
    """Send the media player the command for volume down."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_VOLUME_DOWN, data)


@bind_hass
def mute_volume(hass, mute, entity_id=None):
    """Send the media player the command for muting the volume."""
    data = {ATTR_MEDIA_VOLUME_MUTED: mute}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_VOLUME_MUTE, data)


@bind_hass
def set_volume_level(hass, volume, entity_id=None):
    """Send the media player the command for setting the volume."""
    data = {ATTR_MEDIA_VOLUME_LEVEL: volume}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_VOLUME_SET, data)


@bind_hass
def media_play_pause(hass, entity_id=None):
    """Send the media player the command for play/pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, data)


@bind_hass
def media_play(hass, entity_id=None):
    """Send the media player the command for play/pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_PLAY, data)


@bind_hass
def media_pause(hass, entity_id=None):
    """Send the media player the command for pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_PAUSE, data)


@bind_hass
def media_stop(hass, entity_id=None):
    """Send the media player the command for stop."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_STOP, data)


@bind_hass
def media_next_track(hass, entity_id=None):
    """Send the media player the command for next track."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_NEXT_TRACK, data)


@bind_hass
def media_previous_track(hass, entity_id=None):
    """Send the media player the command for prev track."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, data)


@bind_hass
def media_seek(hass, position, entity_id=None):
    """Send the media player the command to seek in current playing media."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_MEDIA_SEEK_POSITION] = position
    hass.services.call(DOMAIN, SERVICE_MEDIA_SEEK, data)


@bind_hass
def play_media(hass, media_type, media_id, entity_id=None, enqueue=None):
    """Send the media player the command for playing media."""
    data = {ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: media_id}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if enqueue:
        data[ATTR_MEDIA_ENQUEUE] = enqueue

    hass.services.call(DOMAIN, SERVICE_PLAY_MEDIA, data)


@bind_hass
def select_source(hass, source, entity_id=None):
    """Send the media player the command to select input source."""
    data = {ATTR_INPUT_SOURCE: source}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SELECT_SOURCE, data)


@bind_hass
def clear_playlist(hass, entity_id=None):
    """Send the media player the command for clear playlist."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_CLEAR_PLAYLIST, data)
