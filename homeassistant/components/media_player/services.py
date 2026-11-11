"""Services for the media_player integration."""

from collections.abc import Callable
import logging
from typing import Any

import probatio

from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_COMPONENT,
    MEDIA_PLAYER_PLAY_MEDIA_SCHEMA,
    MediaClass,
    MediaPlayerEnqueue,
    MediaPlayerEntityFeature,
    MediaPlayerService,
    MediaPlayerServiceArgument,
    RepeatMode,
)

_LOGGER = logging.getLogger(__name__)


def _promote_media_fields(data: dict[str, Any]) -> dict[str, Any]:
    """If 'media' key exists, promote its fields to the top level."""
    if MediaPlayerServiceArgument.MEDIA in data and isinstance(
        data[MediaPlayerServiceArgument.MEDIA], dict
    ):
        if (
            MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE in data
            or MediaPlayerServiceArgument.MEDIA_CONTENT_ID in data
        ):
            raise probatio.Invalid(
                f"Play media cannot contain '{MediaPlayerServiceArgument.MEDIA}' and "
                f"'{MediaPlayerServiceArgument.MEDIA_CONTENT_ID}' or "
                f"'{MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE}'"
            )
        media_data = data[MediaPlayerServiceArgument.MEDIA]

        if MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE in media_data:
            data[MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE] = media_data[
                MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE
            ]
        if MediaPlayerServiceArgument.MEDIA_CONTENT_ID in media_data:
            data[MediaPlayerServiceArgument.MEDIA_CONTENT_ID] = media_data[
                MediaPlayerServiceArgument.MEDIA_CONTENT_ID
            ]

        del data[MediaPlayerServiceArgument.MEDIA]
    return data


def _rename_keys(**keys: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Create validator that renames keys.

    Necessary because the service schema names do not match the command parameters.

    Async friendly.
    """

    def rename(value: dict[str, Any]) -> dict[str, Any]:
        for to_key, from_key in keys.items():
            if from_key in value:
                value[to_key] = value.pop(from_key)
        return value

    return rename


# Remove in Home Assistant 2022.9
def _rewrite_enqueue(value: dict[str, Any]) -> dict[str, Any]:
    """Rewrite the enqueue value."""
    if MediaPlayerServiceArgument.ENQUEUE not in value:
        pass
    elif value[MediaPlayerServiceArgument.ENQUEUE] is True:
        value[MediaPlayerServiceArgument.ENQUEUE] = MediaPlayerEnqueue.ADD
        _LOGGER.warning(
            "Playing media with enqueue set to True is deprecated. Use 'add' instead"
        )
    elif value[MediaPlayerServiceArgument.ENQUEUE] is False:
        value[MediaPlayerServiceArgument.ENQUEUE] = MediaPlayerEnqueue.PLAY
        _LOGGER.warning(
            "Playing media with enqueue set to False is deprecated. Use 'play' instead"
        )

    return value


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the media_player services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        MediaPlayerService.TURN_ON,
        None,
        "async_turn_on",
        [MediaPlayerEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        MediaPlayerService.TURN_OFF,
        None,
        "async_turn_off",
        [MediaPlayerEntityFeature.TURN_OFF],
    )
    component.async_register_entity_service(
        MediaPlayerService.TOGGLE,
        None,
        "async_toggle",
        [MediaPlayerEntityFeature.TURN_OFF | MediaPlayerEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        MediaPlayerService.VOLUME_UP,
        None,
        "async_volume_up",
        [MediaPlayerEntityFeature.VOLUME_SET, MediaPlayerEntityFeature.VOLUME_STEP],
    )
    component.async_register_entity_service(
        MediaPlayerService.VOLUME_DOWN,
        None,
        "async_volume_down",
        [MediaPlayerEntityFeature.VOLUME_SET, MediaPlayerEntityFeature.VOLUME_STEP],
    )
    component.async_register_entity_service(
        MediaPlayerService.MEDIA_PLAY_PAUSE,
        None,
        "async_media_play_pause",
        [MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE],
    )
    component.async_register_entity_service(
        MediaPlayerService.MEDIA_PLAY,
        None,
        "async_media_play",
        [MediaPlayerEntityFeature.PLAY],
    )
    component.async_register_entity_service(
        MediaPlayerService.MEDIA_PAUSE,
        None,
        "async_media_pause",
        [MediaPlayerEntityFeature.PAUSE],
    )
    component.async_register_entity_service(
        MediaPlayerService.MEDIA_STOP,
        None,
        "async_media_stop",
        [MediaPlayerEntityFeature.STOP],
    )
    component.async_register_entity_service(
        MediaPlayerService.MEDIA_NEXT_TRACK,
        None,
        "async_media_next_track",
        [MediaPlayerEntityFeature.NEXT_TRACK],
    )
    component.async_register_entity_service(
        MediaPlayerService.MEDIA_PREVIOUS_TRACK,
        None,
        "async_media_previous_track",
        [MediaPlayerEntityFeature.PREVIOUS_TRACK],
    )
    component.async_register_entity_service(
        MediaPlayerService.CLEAR_PLAYLIST,
        None,
        "async_clear_playlist",
        [MediaPlayerEntityFeature.CLEAR_PLAYLIST],
    )
    component.async_register_entity_service(
        MediaPlayerService.VOLUME_SET,
        probatio.All(
            cv.make_entity_service_schema(
                {
                    probatio.Required(
                        MediaPlayerServiceArgument.VOLUME_LEVEL
                    ): cv.small_float
                }
            ),
            _rename_keys(volume=MediaPlayerServiceArgument.VOLUME_LEVEL),
        ),
        "async_set_volume_level",
        [MediaPlayerEntityFeature.VOLUME_SET],
    )
    component.async_register_entity_service(
        MediaPlayerService.VOLUME_MUTE,
        probatio.All(
            cv.make_entity_service_schema(
                {
                    probatio.Required(
                        MediaPlayerServiceArgument.IS_VOLUME_MUTED
                    ): cv.boolean
                }
            ),
            _rename_keys(mute=MediaPlayerServiceArgument.IS_VOLUME_MUTED),
        ),
        "async_mute_volume",
        [MediaPlayerEntityFeature.VOLUME_MUTE],
    )
    component.async_register_entity_service(
        MediaPlayerService.MEDIA_SEEK,
        probatio.All(
            cv.make_entity_service_schema(
                {
                    probatio.Required(
                        MediaPlayerServiceArgument.SEEK_POSITION
                    ): cv.positive_float
                }
            ),
            _rename_keys(position=MediaPlayerServiceArgument.SEEK_POSITION),
        ),
        "async_media_seek",
        [MediaPlayerEntityFeature.SEEK],
    )
    component.async_register_entity_service(
        MediaPlayerService.JOIN,
        {
            probatio.Required(MediaPlayerServiceArgument.GROUP_MEMBERS): probatio.All(
                probatio.EnsureList(), [cv.entity_id]
            )
        },
        "async_join_players",
        [MediaPlayerEntityFeature.GROUPING],
    )
    component.async_register_entity_service(
        MediaPlayerService.SELECT_SOURCE,
        {probatio.Required(MediaPlayerServiceArgument.SOURCE): cv.string},
        "async_select_source",
        [MediaPlayerEntityFeature.SELECT_SOURCE],
    )
    component.async_register_entity_service(
        MediaPlayerService.SELECT_SOUND_MODE,
        {probatio.Required(MediaPlayerServiceArgument.SOUND_MODE): cv.string},
        "async_select_sound_mode",
        [MediaPlayerEntityFeature.SELECT_SOUND_MODE],
    )

    component.async_register_entity_service(
        MediaPlayerService.PLAY_MEDIA,
        probatio.All(
            _promote_media_fields,
            cv.make_entity_service_schema(MEDIA_PLAYER_PLAY_MEDIA_SCHEMA),
            _rewrite_enqueue,
            _rename_keys(
                media_type=MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE,
                media_id=MediaPlayerServiceArgument.MEDIA_CONTENT_ID,
                enqueue=MediaPlayerServiceArgument.ENQUEUE,
            ),
        ),
        "async_play_media",
        [MediaPlayerEntityFeature.PLAY_MEDIA],
    )
    component.async_register_entity_service(
        MediaPlayerService.BROWSE_MEDIA,
        {
            probatio.Optional(MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE): cv.string,
            probatio.Optional(MediaPlayerServiceArgument.MEDIA_CONTENT_ID): cv.string,
        },
        "async_browse_media",
        supports_response=SupportsResponse.ONLY,
    )
    component.async_register_entity_service(
        MediaPlayerService.SEARCH_MEDIA,
        {
            probatio.Optional(MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE): cv.string,
            probatio.Optional(MediaPlayerServiceArgument.MEDIA_CONTENT_ID): cv.string,
            probatio.Required(MediaPlayerServiceArgument.SEARCH_QUERY): cv.string,
            probatio.Optional(
                MediaPlayerServiceArgument.MEDIA_FILTER_CLASSES
            ): probatio.All(
                probatio.EnsureList(),
                [probatio.In([m.value for m in MediaClass])],
                lambda x: {MediaClass(item) for item in x},
            ),
        },
        "async_internal_search_media",
        [MediaPlayerEntityFeature.SEARCH_MEDIA],
        SupportsResponse.ONLY,
    )
    component.async_register_entity_service(
        MediaPlayerService.SHUFFLE_SET,
        {probatio.Required(MediaPlayerServiceArgument.SHUFFLE): cv.boolean},
        "async_set_shuffle",
        [MediaPlayerEntityFeature.SHUFFLE_SET],
    )
    component.async_register_entity_service(
        MediaPlayerService.UNJOIN,
        None,
        "async_unjoin_player",
        [MediaPlayerEntityFeature.GROUPING],
    )

    component.async_register_entity_service(
        MediaPlayerService.REPEAT_SET,
        {
            probatio.Required(MediaPlayerServiceArgument.REPEAT): probatio.Coerce(
                RepeatMode
            )
        },
        "async_set_repeat",
        [MediaPlayerEntityFeature.REPEAT_SET],
    )
