"""Support for media browsing."""
import asyncio
import logging

from homeassistant.components.media_player import BrowseError, BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_TYPE_CHANNEL,
)

CHILD_TYPE_MEDIA_CLASS = {
    MEDIA_TYPE_CHANNEL: MEDIA_CLASS_CHANNEL,
}

_LOGGER = logging.getLogger(__name__)


class UnknownMediaType(BrowseError):
    """Unknown media type."""


async def build_item_response(media_library, payload, get_thumbnail_url=None):
    """Create response payload for the provided media query."""
    search_id = payload["search_id"]
    search_type = payload["search_type"]

    _, title, media = await get_media_info(media_library, search_id, search_type)
    if get_thumbnail_url is not None:
        thumbnail = await get_thumbnail_url(search_type, search_id)
    else:
        thumbnail = None

    if media is None:
        return None

    children = await asyncio.gather(
        *(item_payload(item, get_thumbnail_url) for item in media)
    )

    response = BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id=search_id,
        media_content_type=search_type,
        title=title,
        can_play=bool(search_id),
        can_expand=True,
        children=children,
        thumbnail=thumbnail,
    )
    response.calculate_children_class()

    return response


async def item_payload(item, get_thumbnail_url=None):
    """
    Create response payload for a single media item.

    Used by async_browse_media.
    """
    title = item["label"]

    media_class = None

    if "band" in item:
        media_content_type = MEDIA_TYPE_CHANNEL
        media_content_id = f"{item['band']}"
        can_play = True
        can_expand = False
    else:
        # this case is for the top folder of each type
        # possible content types: album, artist, movie, library_music, tvshow, channel
        media_class = MEDIA_CLASS_DIRECTORY
        media_content_type = item["type"]
        media_content_id = ""
        can_play = False
        can_expand = True

    if media_class is None:
        try:
            media_class = CHILD_TYPE_MEDIA_CLASS[media_content_type]
        except KeyError as err:
            _LOGGER.debug("Unknown media type received: %s", media_content_type)
            raise UnknownMediaType from err

    thumbnail = item.get("thumbnail")
    if thumbnail is not None and get_thumbnail_url is not None:
        thumbnail = await get_thumbnail_url(
            media_content_type, media_content_id, thumbnail_url=thumbnail
        )

    return BrowseMedia(
        title=title,
        media_class=media_class,
        media_content_type=media_content_type,
        media_content_id=media_content_id,
        can_play=can_play,
        can_expand=can_expand,
        thumbnail=thumbnail,
    )


async def library_payload():
    """
    Create response payload to describe contents of a specific library.

    Used by async_browse_media.
    """
    library_info = BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        title="Media Library",
        can_play=False,
        can_expand=True,
        children=[],
    )

    library = {
        MEDIA_TYPE_CHANNEL: "Channels",
    }

    library_info.children = await asyncio.gather(
        *(
            item_payload(
                {
                    "label": item["label"],
                    "type": item["type"],
                    "uri": item["type"],
                },
            )
            for item in [
                {"label": name, "type": type_} for type_, name in library.items()
            ]
        )
    )

    return library_info


async def get_media_info(media_library, search_id, search_type):
    """Fetch media/album."""
    thumbnail = None
    title = None
    media = None

    properties = ["thumbnail"]

    if search_type == MEDIA_TYPE_CHANNEL:
        media = await media_library.get_presets()
        title = "Channels"

    return thumbnail, title, media
