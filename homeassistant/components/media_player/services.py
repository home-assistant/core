"""Services for the media_player integration."""

from collections.abc import Callable
import logging
from typing import Any

import probatio

from homeassistant.const import (
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_FILTER_CLASSES,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEARCH_QUERY,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    DATA_COMPONENT,
    MEDIA_PLAYER_PLAY_MEDIA_SCHEMA,
    SERVICE_BROWSE_MEDIA,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_JOIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SEARCH_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    SERVICE_UNJOIN,
    MediaClass,
    MediaPlayerEnqueue,
    MediaPlayerEntityFeature,
    RepeatMode,
)

_LOGGER = logging.getLogger(__name__)


def _promote_media_fields(data: dict[str, Any]) -> dict[str, Any]:
    """If 'media' key exists, promote its fields to the top level."""
    if ATTR_MEDIA in data and isinstance(data[ATTR_MEDIA], dict):
        if ATTR_MEDIA_CONTENT_TYPE in data or ATTR_MEDIA_CONTENT_ID in data:
            raise probatio.Invalid(
                f"Play media cannot contain '{ATTR_MEDIA}' and "
                f"'{ATTR_MEDIA_CONTENT_ID}' or "
                f"'{ATTR_MEDIA_CONTENT_TYPE}'"
            )
        media_data = data[ATTR_MEDIA]

        if ATTR_MEDIA_CONTENT_TYPE in media_data:
            data[ATTR_MEDIA_CONTENT_TYPE] = media_data[ATTR_MEDIA_CONTENT_TYPE]
        if ATTR_MEDIA_CONTENT_ID in media_data:
            data[ATTR_MEDIA_CONTENT_ID] = media_data[ATTR_MEDIA_CONTENT_ID]

        del data[ATTR_MEDIA]
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
    if ATTR_MEDIA_ENQUEUE not in value:
        pass
    elif value[ATTR_MEDIA_ENQUEUE] is True:
        value[ATTR_MEDIA_ENQUEUE] = MediaPlayerEnqueue.ADD
        _LOGGER.warning(
            "Playing media with enqueue set to True is deprecated. Use 'add' instead"
        )
    elif value[ATTR_MEDIA_ENQUEUE] is False:
        value[ATTR_MEDIA_ENQUEUE] = MediaPlayerEnqueue.PLAY
        _LOGGER.warning(
            "Playing media with enqueue set to False is deprecated. Use 'play' instead"
        )

    return value


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the media_player services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_TURN_ON, None, "async_turn_on", [MediaPlayerEntityFeature.TURN_ON]
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, None, "async_turn_off", [MediaPlayerEntityFeature.TURN_OFF]
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE,
        None,
        "async_toggle",
        [MediaPlayerEntityFeature.TURN_OFF | MediaPlayerEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_UP,
        None,
        "async_volume_up",
        [MediaPlayerEntityFeature.VOLUME_SET, MediaPlayerEntityFeature.VOLUME_STEP],
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_DOWN,
        None,
        "async_volume_down",
        [MediaPlayerEntityFeature.VOLUME_SET, MediaPlayerEntityFeature.VOLUME_STEP],
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PLAY_PAUSE,
        None,
        "async_media_play_pause",
        [MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE],
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PLAY, None, "async_media_play", [MediaPlayerEntityFeature.PLAY]
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PAUSE, None, "async_media_pause", [MediaPlayerEntityFeature.PAUSE]
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_STOP, None, "async_media_stop", [MediaPlayerEntityFeature.STOP]
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_NEXT_TRACK,
        None,
        "async_media_next_track",
        [MediaPlayerEntityFeature.NEXT_TRACK],
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_PREVIOUS_TRACK,
        None,
        "async_media_previous_track",
        [MediaPlayerEntityFeature.PREVIOUS_TRACK],
    )
    component.async_register_entity_service(
        SERVICE_CLEAR_PLAYLIST,
        None,
        "async_clear_playlist",
        [MediaPlayerEntityFeature.CLEAR_PLAYLIST],
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_SET,
        probatio.All(
            cv.make_entity_service_schema(
                {probatio.Required(ATTR_MEDIA_VOLUME_LEVEL): cv.small_float}
            ),
            _rename_keys(volume=ATTR_MEDIA_VOLUME_LEVEL),
        ),
        "async_set_volume_level",
        [MediaPlayerEntityFeature.VOLUME_SET],
    )
    component.async_register_entity_service(
        SERVICE_VOLUME_MUTE,
        probatio.All(
            cv.make_entity_service_schema(
                {probatio.Required(ATTR_MEDIA_VOLUME_MUTED): cv.boolean}
            ),
            _rename_keys(mute=ATTR_MEDIA_VOLUME_MUTED),
        ),
        "async_mute_volume",
        [MediaPlayerEntityFeature.VOLUME_MUTE],
    )
    component.async_register_entity_service(
        SERVICE_MEDIA_SEEK,
        probatio.All(
            cv.make_entity_service_schema(
                {probatio.Required(ATTR_MEDIA_SEEK_POSITION): cv.positive_float}
            ),
            _rename_keys(position=ATTR_MEDIA_SEEK_POSITION),
        ),
        "async_media_seek",
        [MediaPlayerEntityFeature.SEEK],
    )
    component.async_register_entity_service(
        SERVICE_JOIN,
        {
            probatio.Required(ATTR_GROUP_MEMBERS): probatio.All(
                cv.ensure_list, [cv.entity_id]
            )
        },
        "async_join_players",
        [MediaPlayerEntityFeature.GROUPING],
    )
    component.async_register_entity_service(
        SERVICE_SELECT_SOURCE,
        {probatio.Required(ATTR_INPUT_SOURCE): cv.string},
        "async_select_source",
        [MediaPlayerEntityFeature.SELECT_SOURCE],
    )
    component.async_register_entity_service(
        SERVICE_SELECT_SOUND_MODE,
        {probatio.Required(ATTR_SOUND_MODE): cv.string},
        "async_select_sound_mode",
        [MediaPlayerEntityFeature.SELECT_SOUND_MODE],
    )

    component.async_register_entity_service(
        SERVICE_PLAY_MEDIA,
        probatio.All(
            _promote_media_fields,
            cv.make_entity_service_schema(MEDIA_PLAYER_PLAY_MEDIA_SCHEMA),
            _rewrite_enqueue,
            _rename_keys(
                media_type=ATTR_MEDIA_CONTENT_TYPE,
                media_id=ATTR_MEDIA_CONTENT_ID,
                enqueue=ATTR_MEDIA_ENQUEUE,
            ),
        ),
        "async_play_media",
        [MediaPlayerEntityFeature.PLAY_MEDIA],
    )
    component.async_register_entity_service(
        SERVICE_BROWSE_MEDIA,
        {
            probatio.Optional(ATTR_MEDIA_CONTENT_TYPE): cv.string,
            probatio.Optional(ATTR_MEDIA_CONTENT_ID): cv.string,
        },
        "async_browse_media",
        supports_response=SupportsResponse.ONLY,
    )
    component.async_register_entity_service(
        SERVICE_SEARCH_MEDIA,
        {
            probatio.Optional(ATTR_MEDIA_CONTENT_TYPE): cv.string,
            probatio.Optional(ATTR_MEDIA_CONTENT_ID): cv.string,
            probatio.Required(ATTR_MEDIA_SEARCH_QUERY): cv.string,
            probatio.Optional(ATTR_MEDIA_FILTER_CLASSES): probatio.All(
                cv.ensure_list,
                [probatio.In([m.value for m in MediaClass])],
                lambda x: {MediaClass(item) for item in x},
            ),
        },
        "async_internal_search_media",
        [MediaPlayerEntityFeature.SEARCH_MEDIA],
        SupportsResponse.ONLY,
    )
    component.async_register_entity_service(
        SERVICE_SHUFFLE_SET,
        {probatio.Required(ATTR_MEDIA_SHUFFLE): cv.boolean},
        "async_set_shuffle",
        [MediaPlayerEntityFeature.SHUFFLE_SET],
    )
    component.async_register_entity_service(
        SERVICE_UNJOIN, None, "async_unjoin_player", [MediaPlayerEntityFeature.GROUPING]
    )

    component.async_register_entity_service(
        SERVICE_REPEAT_SET,
        {probatio.Required(ATTR_MEDIA_REPEAT): probatio.Coerce(RepeatMode)},
        "async_set_repeat",
        [MediaPlayerEntityFeature.REPEAT_SET],
    )
