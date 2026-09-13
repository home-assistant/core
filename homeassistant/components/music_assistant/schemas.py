"""Probatio schemas for Music Assistant integration service responses."""

from typing import TYPE_CHECKING, Any

from music_assistant_models.enums import ImageType, MediaType
from music_assistant_models.media_items import ItemMapping
import probatio

from homeassistant.const import ATTR_NAME
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_ACTIVE,
    ATTR_ALBUM,
    ATTR_ALBUMS,
    ATTR_ARTISTS,
    ATTR_AUDIOBOOKS,
    ATTR_BIT_DEPTH,
    ATTR_BITRATE,
    ATTR_CONTENT_TYPE,
    ATTR_CURRENT_INDEX,
    ATTR_CURRENT_ITEM,
    ATTR_DISCART_IMAGE,
    ATTR_DURATION,
    ATTR_ELAPSED_TIME,
    ATTR_EXPLICIT,
    ATTR_FANART_IMAGE,
    ATTR_FAVORITE,
    ATTR_IMAGE,
    ATTR_ITEM_ID,
    ATTR_ITEMS,
    ATTR_LIMIT,
    ATTR_MEDIA_ITEM,
    ATTR_MEDIA_TYPE,
    ATTR_NEXT_ITEM,
    ATTR_OFFSET,
    ATTR_ORDER_BY,
    ATTR_PLAYLISTS,
    ATTR_PODCASTS,
    ATTR_PROVIDER,
    ATTR_QUEUE_ID,
    ATTR_QUEUE_ITEM_ID,
    ATTR_RADIO,
    ATTR_REPEAT_MODE,
    ATTR_SAMPLE_RATE,
    ATTR_SHUFFLE_ENABLED,
    ATTR_STREAM_DETAILS,
    ATTR_STREAM_TITLE,
    ATTR_TRACKS,
    ATTR_URI,
    ATTR_VERSION,
)

if TYPE_CHECKING:
    from music_assistant_client import MusicAssistantClient
    from music_assistant_models.media_items import MediaItemType
    from music_assistant_models.queue_item import QueueItem

MEDIA_ITEM_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_MEDIA_TYPE): probatio.Coerce(MediaType),
        probatio.Required(ATTR_URI): cv.string,
        probatio.Required(ATTR_NAME): cv.string,
        probatio.Required(ATTR_VERSION): cv.string,
        probatio.Required(ATTR_IMAGE, default=None): probatio.Any(None, cv.string),
        probatio.Optional(ATTR_FAVORITE): bool,
        probatio.Optional(ATTR_EXPLICIT): probatio.Any(None, bool),
        probatio.Optional(ATTR_DISCART_IMAGE): probatio.Any(None, cv.string),
        probatio.Optional(ATTR_FANART_IMAGE): probatio.Any(None, cv.string),
        probatio.Optional(ATTR_ARTISTS): [probatio.Self],
        probatio.Optional(ATTR_ALBUM): probatio.Self,
    }
)


def media_item_dict_from_mass_item(
    mass: MusicAssistantClient,
    item: MediaItemType | ItemMapping,
) -> dict[str, Any]:
    """Parse a Music Assistant MediaItem."""
    result: dict[str, Any] = {
        ATTR_MEDIA_TYPE: item.media_type,
        ATTR_URI: item.uri,
        ATTR_NAME: item.name,
        ATTR_VERSION: item.version,
        ATTR_IMAGE: mass.get_media_item_image_url(item),
    }

    if isinstance(item, ItemMapping):
        return result

    result[ATTR_FAVORITE] = item.favorite
    result[ATTR_EXPLICIT] = item.metadata.explicit

    if item.media_type is MediaType.ALBUM:
        result[ATTR_DISCART_IMAGE] = mass.get_media_item_image_url(
            item, type=ImageType.DISCART
        )
    if item.media_type is MediaType.ARTIST:
        result[ATTR_FANART_IMAGE] = mass.get_media_item_image_url(
            item, type=ImageType.FANART
        )

    artists: list[ItemMapping] | None
    if artists := getattr(item, "artists", None):
        result[ATTR_ARTISTS] = [
            media_item_dict_from_mass_item(mass, x) for x in artists
        ]
    album: ItemMapping | None
    if album := getattr(item, "album", None):
        result[ATTR_ALBUM] = media_item_dict_from_mass_item(mass, album)

    return result


SEARCH_RESULT_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_ARTISTS): probatio.All(
            cv.ensure_list, [probatio.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        probatio.Required(ATTR_ALBUMS): probatio.All(
            cv.ensure_list, [probatio.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        probatio.Required(ATTR_TRACKS): probatio.All(
            cv.ensure_list, [probatio.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        probatio.Required(ATTR_PLAYLISTS): probatio.All(
            cv.ensure_list, [probatio.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        probatio.Required(ATTR_RADIO): probatio.All(
            cv.ensure_list, [probatio.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        probatio.Required(ATTR_AUDIOBOOKS): probatio.All(
            cv.ensure_list, [probatio.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        probatio.Required(ATTR_PODCASTS): probatio.All(
            cv.ensure_list, [probatio.Schema(MEDIA_ITEM_SCHEMA)]
        ),
    },
)

LIBRARY_RESULTS_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_ITEMS): probatio.All(
            cv.ensure_list, [probatio.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        probatio.Required(ATTR_LIMIT): int,
        probatio.Required(ATTR_OFFSET): int,
        probatio.Required(ATTR_ORDER_BY): str,
        probatio.Required(ATTR_MEDIA_TYPE): probatio.Coerce(MediaType),
    }
)

AUDIO_FORMAT_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_PROVIDER): str,
        probatio.Required(ATTR_ITEM_ID): str,
        probatio.Required(ATTR_CONTENT_TYPE): str,
        probatio.Required(ATTR_SAMPLE_RATE): int,
        probatio.Required(ATTR_BIT_DEPTH): int,
        probatio.Optional(ATTR_BITRATE): int,
    }
)

QUEUE_ITEM_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_QUEUE_ITEM_ID): cv.string,
        probatio.Required(ATTR_NAME): cv.string,
        probatio.Optional(ATTR_DURATION, default=None): probatio.Any(None, int),
        probatio.Optional(ATTR_MEDIA_ITEM, default=None): probatio.Any(
            None, probatio.Schema(MEDIA_ITEM_SCHEMA)
        ),
        probatio.Optional(ATTR_STREAM_TITLE, default=None): probatio.Any(
            None, cv.string
        ),
        probatio.Optional(ATTR_STREAM_DETAILS): probatio.Schema(AUDIO_FORMAT_SCHEMA),
    }
)


def queue_item_dict_from_mass_item(
    mass: MusicAssistantClient,
    item: QueueItem | None,
) -> dict[str, Any] | None:
    """Parse a Music Assistant QueueItem."""
    if not item:
        return None
    result = {
        ATTR_QUEUE_ITEM_ID: item.queue_item_id,
        ATTR_NAME: item.name,
        ATTR_DURATION: item.duration,
        ATTR_MEDIA_ITEM: (
            media_item_dict_from_mass_item(mass, item.media_item)
            if item.media_item
            else None
        ),
    }
    if streamdetails := item.streamdetails:
        result[ATTR_STREAM_TITLE] = streamdetails.stream_title
        stream_details_dict: dict[str, Any] = {
            ATTR_PROVIDER: streamdetails.provider,
            ATTR_ITEM_ID: streamdetails.item_id,
            ATTR_CONTENT_TYPE: streamdetails.audio_format.content_type.value,
            ATTR_SAMPLE_RATE: streamdetails.audio_format.sample_rate,
            ATTR_BIT_DEPTH: streamdetails.audio_format.bit_depth,
        }
        if streamdetails.audio_format.bit_rate is not None:
            stream_details_dict[ATTR_BITRATE] = streamdetails.audio_format.bit_rate
        result[ATTR_STREAM_DETAILS] = stream_details_dict

    return result


QUEUE_DETAILS_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_QUEUE_ID): str,
        probatio.Required(ATTR_ACTIVE): bool,
        probatio.Required(ATTR_NAME): str,
        probatio.Required(ATTR_ITEMS): int,
        probatio.Required(ATTR_SHUFFLE_ENABLED): bool,
        probatio.Required(ATTR_REPEAT_MODE): str,
        probatio.Required(ATTR_CURRENT_INDEX): probatio.Any(None, int),
        probatio.Required(ATTR_ELAPSED_TIME): probatio.Coerce(int),
        probatio.Required(ATTR_CURRENT_ITEM): probatio.Any(None, QUEUE_ITEM_SCHEMA),
        probatio.Required(ATTR_NEXT_ITEM): probatio.Any(None, QUEUE_ITEM_SCHEMA),
    }
)
