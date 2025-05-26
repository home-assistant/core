"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEnqueue,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import HomeAssistant
from homeassistant.loader import bind_hass


async def async_turn_on(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Turn on specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)


@bind_hass
def turn_on(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Turn on specified media player or all."""
    hass.add_job(async_turn_on, hass, entity_id)


async def async_turn_off(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Turn off specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)


@bind_hass
def turn_off(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Turn off specified media player or all."""
    hass.add_job(async_turn_off, hass, entity_id)


async def async_toggle(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Toggle specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TOGGLE, data, blocking=True)


@bind_hass
def toggle(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Toggle specified media player or all."""
    hass.add_job(async_toggle, hass, entity_id)


async def async_volume_up(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for volume up."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_VOLUME_UP, data, blocking=True)


@bind_hass
def volume_up(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for volume up."""
    hass.add_job(async_volume_up, hass, entity_id)


async def async_volume_down(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for volume down."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_VOLUME_DOWN, data, blocking=True)


@bind_hass
def volume_down(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for volume down."""
    hass.add_job(async_volume_down, hass, entity_id)


async def async_mute_volume(
    hass: HomeAssistant, mute: bool, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for muting the volume."""
    data = {ATTR_MEDIA_VOLUME_MUTED: mute}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_VOLUME_MUTE, data, blocking=True)


@bind_hass
def mute_volume(
    hass: HomeAssistant, mute: bool, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for muting the volume."""
    hass.add_job(async_mute_volume, hass, mute, entity_id)


async def async_set_volume_level(
    hass: HomeAssistant, volume: float, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for setting the volume."""
    data = {ATTR_MEDIA_VOLUME_LEVEL: volume}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_VOLUME_SET, data, blocking=True)


@bind_hass
def set_volume_level(
    hass: HomeAssistant, volume: float, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for setting the volume."""
    hass.add_job(async_set_volume_level, hass, volume, entity_id)


async def async_media_play_pause(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for play/pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, data, blocking=True
    )


@bind_hass
def media_play_pause(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for play/pause."""
    hass.add_job(async_media_play_pause, hass, entity_id)


async def async_media_play(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for play/pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_MEDIA_PLAY, data, blocking=True)


@bind_hass
def media_play(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for play/pause."""
    hass.add_job(async_media_play, hass, entity_id)


async def async_media_pause(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_MEDIA_PAUSE, data, blocking=True)


@bind_hass
def media_pause(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for pause."""
    hass.add_job(async_media_pause, hass, entity_id)


async def async_media_stop(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for stop."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_MEDIA_STOP, data, blocking=True)


@bind_hass
def media_stop(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for stop."""
    hass.add_job(async_media_stop, hass, entity_id)


async def async_media_next_track(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for next track."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_NEXT_TRACK, data, blocking=True
    )


@bind_hass
def media_next_track(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for next track."""
    hass.add_job(async_media_next_track, hass, entity_id)


async def async_media_previous_track(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for prev track."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, data, blocking=True
    )


@bind_hass
def media_previous_track(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for prev track."""
    hass.add_job(async_media_previous_track, hass, entity_id)


async def async_media_seek(
    hass: HomeAssistant, position: float, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command to seek in current playing media."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_MEDIA_SEEK_POSITION] = position
    await hass.services.async_call(DOMAIN, SERVICE_MEDIA_SEEK, data, blocking=True)


@bind_hass
def media_seek(
    hass: HomeAssistant, position: float, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command to seek in current playing media."""
    hass.add_job(async_media_seek, hass, position, entity_id)


async def async_play_media(
    hass: HomeAssistant,
    media_type: str,
    media_id: str,
    entity_id: str = ENTITY_MATCH_ALL,
    enqueue: MediaPlayerEnqueue | bool | None = None,
) -> None:
    """Send the media player the command for playing media."""
    data = {ATTR_MEDIA_CONTENT_TYPE: media_type, ATTR_MEDIA_CONTENT_ID: media_id}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if enqueue:
        data[ATTR_MEDIA_ENQUEUE] = enqueue

    await hass.services.async_call(DOMAIN, SERVICE_PLAY_MEDIA, data, blocking=True)


@bind_hass
def play_media(
    hass: HomeAssistant,
    media_type: str,
    media_id: str,
    entity_id: str = ENTITY_MATCH_ALL,
    enqueue: MediaPlayerEnqueue | bool | None = None,
) -> None:
    """Send the media player the command for playing media."""
    hass.add_job(async_play_media, hass, media_type, media_id, entity_id, enqueue)


async def async_select_source(
    hass: HomeAssistant, source: str, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command to select input source."""
    data = {ATTR_INPUT_SOURCE: source}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_SELECT_SOURCE, data, blocking=True)


@bind_hass
def select_source(
    hass: HomeAssistant, source: str, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command to select input source."""
    hass.add_job(async_select_source, hass, source, entity_id)


async def async_clear_playlist(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for clear playlist."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_CLEAR_PLAYLIST, data, blocking=True)


@bind_hass
def clear_playlist(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for clear playlist."""
    hass.add_job(async_clear_playlist, hass, entity_id)
