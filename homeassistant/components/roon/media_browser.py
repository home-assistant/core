"""Support to interface with the Plex API."""
import logging

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_TRACK,
)
from homeassistant.components.media_player.errors import BrowseError


class UnknownMediaType(BrowseError):
    """Unknown media type."""


EXPANDABLES = ["album", "artist", "playlist"]
PLAYLISTS_BROWSE_PAYLOAD = {
    "title": "Playlists",
    "media_class": MEDIA_CLASS_DIRECTORY,
    "media_content_id": "all",
    "media_content_type": "playlists",
    "can_play": False,
    "can_expand": True,
}

ITEM_TYPE_MEDIA_CLASS = {
    "album": MEDIA_CLASS_ALBUM,
    "artist": MEDIA_CLASS_ARTIST,
    "playlist": MEDIA_CLASS_PLAYLIST,
    "track": MEDIA_CLASS_TRACK,
}

UNPLAYABLE_ITEMS = {
    "Play Album",
    "Play Artist",
    "Play Playlist",
    "Play Now",
    "Play From Here",
    "Queue",
    "Start Radio",
    "Add Next",
    "Play Radio",
    "Settings",
}

_LOGGER = logging.getLogger(__name__)


def browse_media(zone_id, roon_server, media_content_type=None, media_content_id=None):
    """Implement the websocket media browsing helper."""
    try:
        _LOGGER.warning("browse_media: %s: %s", media_content_type, media_content_id)
        if media_content_type in [None, "library"]:
            return library_payload(roon_server, zone_id, media_content_id)

    except UnknownMediaType as err:
        raise BrowseError(
            f"Media not found: {media_content_type} / {media_content_id}"
        ) from err


def item_payload(roon_server, item):
    """Create response payload for a single media item."""

    title = item.get("title")
    subtitle = item.get("subtitle")
    if subtitle is None:
        display_title = title
    else:
        display_title = f"{title} - {subtitle}"

    image_id = item.get("image_key")
    if image_id is None:
        image = None
    else:
        image = roon_server.roonapi.get_image(image_id)

    media_content_id = item.get("item_key")

    can_play = True
    can_expand = True
    media_class = MEDIA_CLASS_TRACK
    hint = item.get("hint")
    if hint == "list":
        can_play = True
        can_expand = True
        media_class = MEDIA_CLASS_DIRECTORY
    elif hint == "action_list":
        can_play = True
        can_expand = True
        media_class = MEDIA_CLASS_PLAYLIST
    elif hint == "action":
        can_play = True
        can_expand = True
        media_class = MEDIA_CLASS_TRACK

    if title in UNPLAYABLE_ITEMS:
        _LOGGER.debug("Skipping %s", title)
        return None

    payload = {
        "title": display_title,
        "media_class": media_class,
        "media_content_id": media_content_id,
        "media_content_type": "library",
        "can_play": can_play,
        "can_expand": can_expand,
        "thumbnail": image,
    }

    return BrowseMedia(**payload)


def library_payload(roon_server, zone_id, media_content_id):
    """Create response payload for the library."""

    library_info = BrowseMedia(
        title="Media Library",
        media_content_id="library",
        media_content_type="library",
        media_class=MEDIA_CLASS_DIRECTORY,
        can_play=False,
        can_expand=True,
        children=[],
    )

    opts = {
        "hierarchy": "browse",
        "zone_or_output_id": zone_id,
    }

    # Roon starts browsing for a zone where it left off - so start from the top unless otherwise specified
    if media_content_id is None or media_content_id == "library":
        opts["pop_all"] = True
    else:
        opts["item_key"] = media_content_id

    # _LOGGER.error(opts)
    res1 = roon_server.roonapi.browse_browse(opts)
    _LOGGER.error(res1)
    result = roon_server.roonapi.browse_load(opts)
    # _LOGGER.error(result)

    for item in result["items"]:
        _LOGGER.warn(item)
        item = item_payload(roon_server, item)
        if not (item is None):
            library_info.children.append(item)

    return library_info
