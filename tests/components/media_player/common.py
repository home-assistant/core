"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.media_player import (
    DOMAIN,
    MediaPlayerEnqueue,
    MediaPlayerService,
    MediaPlayerServiceArgument,
)
from homeassistant.const import ENTITY_MATCH_ALL, TargetKey
from homeassistant.core import HomeAssistant


async def async_turn_on(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Turn on specified media player or all."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.TURN_ON, data, blocking=True
    )


def turn_on(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Turn on specified media player or all."""
    hass.add_job(async_turn_on, hass, entity_id)


async def async_turn_off(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Turn off specified media player or all."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.TURN_OFF, data, blocking=True
    )


def turn_off(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Turn off specified media player or all."""
    hass.add_job(async_turn_off, hass, entity_id)


async def async_toggle(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Toggle specified media player or all."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.TOGGLE, data, blocking=True
    )


def toggle(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Toggle specified media player or all."""
    hass.add_job(async_toggle, hass, entity_id)


async def async_volume_up(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for volume up."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.VOLUME_UP, data, blocking=True
    )


def volume_up(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for volume up."""
    hass.add_job(async_volume_up, hass, entity_id)


async def async_volume_down(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for volume down."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.VOLUME_DOWN, data, blocking=True
    )


def volume_down(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for volume down."""
    hass.add_job(async_volume_down, hass, entity_id)


async def async_mute_volume(
    hass: HomeAssistant, mute: bool, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for muting the volume."""
    data = {MediaPlayerServiceArgument.IS_VOLUME_MUTED: mute}

    if entity_id:
        data[TargetKey.ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, MediaPlayerService.VOLUME_MUTE, data, blocking=True
    )


def mute_volume(
    hass: HomeAssistant, mute: bool, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for muting the volume."""
    hass.add_job(async_mute_volume, hass, mute, entity_id)


async def async_set_volume_level(
    hass: HomeAssistant, volume: float, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for setting the volume."""
    data = {MediaPlayerServiceArgument.VOLUME_LEVEL: volume}

    if entity_id:
        data[TargetKey.ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, MediaPlayerService.VOLUME_SET, data, blocking=True
    )


def set_volume_level(
    hass: HomeAssistant, volume: float, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for setting the volume."""
    hass.add_job(async_set_volume_level, hass, volume, entity_id)


async def async_media_play_pause(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for play/pause."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.MEDIA_PLAY_PAUSE, data, blocking=True
    )


def media_play_pause(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for play/pause."""
    hass.add_job(async_media_play_pause, hass, entity_id)


async def async_media_play(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for play/pause."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.MEDIA_PLAY, data, blocking=True
    )


def media_play(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for play/pause."""
    hass.add_job(async_media_play, hass, entity_id)


async def async_media_pause(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for pause."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.MEDIA_PAUSE, data, blocking=True
    )


def media_pause(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for pause."""
    hass.add_job(async_media_pause, hass, entity_id)


async def async_media_stop(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for stop."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.MEDIA_STOP, data, blocking=True
    )


def media_stop(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for stop."""
    hass.add_job(async_media_stop, hass, entity_id)


async def async_media_next_track(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for next track."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.MEDIA_NEXT_TRACK, data, blocking=True
    )


def media_next_track(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for next track."""
    hass.add_job(async_media_next_track, hass, entity_id)


async def async_media_previous_track(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for prev track."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.MEDIA_PREVIOUS_TRACK, data, blocking=True
    )


def media_previous_track(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for prev track."""
    hass.add_job(async_media_previous_track, hass, entity_id)


async def async_media_seek(
    hass: HomeAssistant, position: float, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command to seek in current playing media."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    data[MediaPlayerServiceArgument.SEEK_POSITION] = position
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.MEDIA_SEEK, data, blocking=True
    )


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
    data = {
        MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE: media_type,
        MediaPlayerServiceArgument.MEDIA_CONTENT_ID: media_id,
    }

    if entity_id:
        data[TargetKey.ENTITY_ID] = entity_id

    if enqueue:
        data[MediaPlayerServiceArgument.ENQUEUE] = enqueue

    await hass.services.async_call(
        DOMAIN, MediaPlayerService.PLAY_MEDIA, data, blocking=True
    )


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
    data = {MediaPlayerServiceArgument.SOURCE: source}

    if entity_id:
        data[TargetKey.ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, MediaPlayerService.SELECT_SOURCE, data, blocking=True
    )


def select_source(
    hass: HomeAssistant, source: str, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command to select input source."""
    hass.add_job(async_select_source, hass, source, entity_id)


async def async_clear_playlist(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Send the media player the command for clear playlist."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(
        DOMAIN, MediaPlayerService.CLEAR_PLAYLIST, data, blocking=True
    )


def clear_playlist(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Send the media player the command for clear playlist."""
    hass.add_job(async_clear_playlist, hass, entity_id)
