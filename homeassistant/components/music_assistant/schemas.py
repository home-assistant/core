"""Voluptuous schemas for Music Assistant integration service responses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from music_assistant_models.enums import MediaType
import voluptuous as vol

from homeassistant.const import ATTR_NAME
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_ACTIVE,
    ATTR_ALBUM,
    ATTR_ALBUMS,
    ATTR_ARTISTS,
    ATTR_AUDIOBOOKS,
    ATTR_BIT_DEPTH,
    ATTR_CONTENT_TYPE,
    ATTR_CURRENT_INDEX,
    ATTR_CURRENT_ITEM,
    ATTR_DURATION,
    ATTR_ELAPSED_TIME,
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
    from music_assistant_models.media_items import ItemMapping, MediaItemType
    from music_assistant_models.queue_item import QueueItem

MEDIA_ITEM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MEDIA_TYPE): vol.Coerce(MediaType),
        vol.Required(ATTR_URI): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_VERSION): cv.string,
        vol.Optional(ATTR_IMAGE, default=None): vol.Any(None, cv.string),
        vol.Optional(ATTR_ARTISTS): [vol.Self],
        vol.Optional(ATTR_ALBUM): vol.Self,
    }
)


def media_item_dict_from_mass_item(
    mass: MusicAssistantClient,
    item: MediaItemType | ItemMapping,
) -> dict[str, Any]:
    """Parse a Music Assistant MediaItem."""
    base: dict[str, Any] = {
        ATTR_MEDIA_TYPE: item.media_type,
        ATTR_URI: item.uri,
        ATTR_NAME: item.name,
        ATTR_VERSION: item.version,
        ATTR_IMAGE: mass.get_media_item_image_url(item),
    }
    artists: list[ItemMapping] | None
    if artists := getattr(item, "artists", None):
        base[ATTR_ARTISTS] = [media_item_dict_from_mass_item(mass, x) for x in artists]
    album: ItemMapping | None
    if album := getattr(item, "album", None):
        base[ATTR_ALBUM] = media_item_dict_from_mass_item(mass, album)
    return base


SEARCH_RESULT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ARTISTS): vol.All(
            cv.ensure_list, [vol.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        vol.Required(ATTR_ALBUMS): vol.All(
            cv.ensure_list, [vol.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        vol.Required(ATTR_TRACKS): vol.All(
            cv.ensure_list, [vol.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        vol.Required(ATTR_PLAYLISTS): vol.All(
            cv.ensure_list, [vol.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        vol.Required(ATTR_RADIO): vol.All(
            cv.ensure_list, [vol.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        vol.Required(ATTR_AUDIOBOOKS): vol.All(
            cv.ensure_list, [vol.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        vol.Required(ATTR_PODCASTS): vol.All(
            cv.ensure_list, [vol.Schema(MEDIA_ITEM_SCHEMA)]
        ),
    },
)

LIBRARY_RESULTS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ITEMS): vol.All(
            cv.ensure_list, [vol.Schema(MEDIA_ITEM_SCHEMA)]
        ),
        vol.Required(ATTR_LIMIT): int,
        vol.Required(ATTR_OFFSET): int,
        vol.Required(ATTR_ORDER_BY): str,
        vol.Required(ATTR_MEDIA_TYPE): vol.Coerce(MediaType),
    }
)

AUDIO_FORMAT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONTENT_TYPE): str,
        vol.Required(ATTR_SAMPLE_RATE): int,
        vol.Required(ATTR_BIT_DEPTH): int,
        vol.Required(ATTR_PROVIDER): str,
        vol.Required(ATTR_ITEM_ID): str,
    }
)

QUEUE_ITEM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_QUEUE_ITEM_ID): cv.string,
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_DURATION, default=None): vol.Any(None, int),
        vol.Optional(ATTR_MEDIA_ITEM, default=None): vol.Any(
            None, vol.Schema(MEDIA_ITEM_SCHEMA)
        ),
        vol.Optional(ATTR_STREAM_DETAILS): vol.Schema(AUDIO_FORMAT_SCHEMA),
        vol.Optional(ATTR_STREAM_TITLE, default=None): vol.Any(None, cv.string),
    }
)


def queue_item_dict_from_mass_item(
    mass: MusicAssistantClient,
    item: QueueItem | None,
) -> dict[str, Any] | None:
    """Parse a Music Assistant QueueItem."""
    if not item:
        return None
    base = {
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
        base[ATTR_STREAM_TITLE] = streamdetails.stream_title
        base[ATTR_STREAM_DETAILS] = {
            ATTR_CONTENT_TYPE: streamdetails.audio_format.content_type.value,
            ATTR_SAMPLE_RATE: streamdetails.audio_format.sample_rate,
            ATTR_BIT_DEPTH: streamdetails.audio_format.bit_depth,
            ATTR_PROVIDER: streamdetails.provider,
            ATTR_ITEM_ID: streamdetails.item_id,
        }

    return base


QUEUE_DETAILS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_QUEUE_ID): str,
        vol.Required(ATTR_ACTIVE): bool,
        vol.Required(ATTR_NAME): str,
        vol.Required(ATTR_ITEMS): int,
        vol.Required(ATTR_SHUFFLE_ENABLED): bool,
        vol.Required(ATTR_REPEAT_MODE): str,
        vol.Required(ATTR_CURRENT_INDEX): vol.Any(None, int),
        vol.Required(ATTR_ELAPSED_TIME): vol.Coerce(int),
        vol.Required(ATTR_CURRENT_ITEM): vol.Any(None, QUEUE_ITEM_SCHEMA),
        vol.Required(ATTR_NEXT_ITEM): vol.Any(None, QUEUE_ITEM_SCHEMA),
    }
)
