"""Support for media browsing."""
from contextlib import suppress
import logging
import urllib.parse

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_TYPE_ALBUM,
)
from homeassistant.components.media_player.errors import BrowseError

from .const import (
    EXPANDABLE_MEDIA_TYPES,
    LIBRARY_TITLES_MAPPING,
    MEDIA_TYPES_TO_SONOS,
    PLAYABLE_MEDIA_TYPES,
    SONOS_ALBUM,
    SONOS_ALBUM_ARTIST,
    SONOS_GENRE,
    SONOS_TO_MEDIA_CLASSES,
    SONOS_TO_MEDIA_TYPES,
    SONOS_TRACKS,
    SONOS_TYPES_MAPPING,
)
from .exception import UnknownMediaType

_LOGGER = logging.getLogger(__name__)


def build_item_response(media_library, payload, get_thumbnail_url=None):
    """Create response payload for the provided media query."""
    if payload["search_type"] == MEDIA_TYPE_ALBUM and payload["idstring"].startswith(
        ("A:GENRE", "A:COMPOSER")
    ):
        payload["idstring"] = "A:ALBUMARTIST/" + "/".join(
            payload["idstring"].split("/")[2:]
        )

    media = media_library.browse_by_idstring(
        MEDIA_TYPES_TO_SONOS[payload["search_type"]],
        payload["idstring"],
        full_album_art_uri=True,
        max_items=0,
    )

    if media is None:
        return

    thumbnail = None
    title = None

    # Fetch album info for titles and thumbnails
    # Can't be extracted from track info
    if (
        payload["search_type"] == MEDIA_TYPE_ALBUM
        and media[0].item_class == "object.item.audioItem.musicTrack"
    ):
        item = get_media(media_library, payload["idstring"], SONOS_ALBUM_ARTIST)
        title = getattr(item, "title", None)
        thumbnail = get_thumbnail_url(SONOS_ALBUM_ARTIST, payload["idstring"])

    if not title:
        try:
            title = urllib.parse.unquote(payload["idstring"].split("/")[1])
        except IndexError:
            title = LIBRARY_TITLES_MAPPING[payload["idstring"]]

    try:
        media_class = SONOS_TO_MEDIA_CLASSES[
            MEDIA_TYPES_TO_SONOS[payload["search_type"]]
        ]
    except KeyError:
        _LOGGER.debug("Unknown media type received %s", payload["search_type"])
        return None

    children = []
    for item in media:
        with suppress(UnknownMediaType):
            children.append(item_payload(item, get_thumbnail_url))

    return BrowseMedia(
        title=title,
        thumbnail=thumbnail,
        media_class=media_class,
        media_content_id=payload["idstring"],
        media_content_type=payload["search_type"],
        children=children,
        can_play=can_play(payload["search_type"]),
        can_expand=can_expand(payload["search_type"]),
    )


def item_payload(item, get_thumbnail_url=None):
    """
    Create response payload for a single media item.

    Used by async_browse_media.
    """
    media_type = get_media_type(item)
    try:
        media_class = SONOS_TO_MEDIA_CLASSES[media_type]
    except KeyError as err:
        _LOGGER.debug("Unknown media type received %s", media_type)
        raise UnknownMediaType from err

    content_id = get_content_id(item)
    thumbnail = None
    if getattr(item, "album_art_uri", None):
        thumbnail = get_thumbnail_url(media_class, content_id)

    return BrowseMedia(
        title=item.title,
        thumbnail=thumbnail,
        media_class=media_class,
        media_content_id=content_id,
        media_content_type=SONOS_TO_MEDIA_TYPES[media_type],
        can_play=can_play(item.item_class),
        can_expand=can_expand(item),
    )


def library_payload(media_library, get_thumbnail_url=None):
    """
    Create response payload to describe contents of a specific library.

    Used by async_browse_media.
    """
    if not media_library.browse_by_idstring(
        "tracks",
        "",
        max_items=1,
    ):
        raise BrowseError("Local library not found")

    children = []
    for item in media_library.browse():
        with suppress(UnknownMediaType):
            children.append(item_payload(item, get_thumbnail_url))

    return BrowseMedia(
        title="Music Library",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        can_play=False,
        can_expand=True,
        children=children,
    )


def get_media_type(item):
    """Extract media type of item."""
    if item.item_class == "object.item.audioItem.musicTrack":
        return SONOS_TRACKS

    if (
        item.item_class == "object.container.album.musicAlbum"
        and SONOS_TYPES_MAPPING.get(item.item_id.split("/")[0])
        in [
            SONOS_ALBUM_ARTIST,
            SONOS_GENRE,
        ]
    ):
        return SONOS_TYPES_MAPPING[item.item_class]

    return SONOS_TYPES_MAPPING.get(item.item_id.split("/")[0], item.item_class)


def can_play(item):
    """
    Test if playable.

    Used by async_browse_media.
    """
    return SONOS_TO_MEDIA_TYPES.get(item) in PLAYABLE_MEDIA_TYPES


def can_expand(item):
    """
    Test if expandable.

    Used by async_browse_media.
    """
    if isinstance(item, str):
        return SONOS_TYPES_MAPPING.get(item) in EXPANDABLE_MEDIA_TYPES

    if SONOS_TO_MEDIA_TYPES.get(item.item_class) in EXPANDABLE_MEDIA_TYPES:
        return True

    return SONOS_TYPES_MAPPING.get(item.item_id) in EXPANDABLE_MEDIA_TYPES


def get_content_id(item):
    """Extract content id or uri."""
    if item.item_class == "object.item.audioItem.musicTrack":
        return item.get_uri()
    return item.item_id


def get_media(media_library, item_id, search_type):
    """Fetch media/album."""
    search_type = MEDIA_TYPES_TO_SONOS.get(search_type, search_type)

    if not item_id.startswith("A:ALBUM") and search_type == SONOS_ALBUM:
        item_id = "A:ALBUMARTIST/" + "/".join(item_id.split("/")[2:])

    for item in media_library.browse_by_idstring(
        search_type,
        "/".join(item_id.split("/")[:-1]),
        full_album_art_uri=True,
        max_items=0,
    ):
        if item.item_id == item_id:
            return item
