"""Support for media browsing."""

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_APP,
    MEDIA_TYPE_APPS,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_CHANNELS,
)

PLAYABLE_MEDIA_TYPES = [
    MEDIA_TYPE_APP,
    MEDIA_TYPE_CHANNEL,
]

 EXPANDABLE_MEDIA_TYPES = [
    MEDIA_TYPE_APPS,
    MEDIA_TYPE_CHANNELS,
]


async def item_payload(item, media_library):
    """
    Create response payload for a single media item.

    Used by async_browse_media.
    """
    if "app_id" in item:
        media_content_type = MEDIA_TYPE_APP
        media_content_id = f"{item.app_id}"
    elif "number" in item:
        media_content_type = MEDIA_TYPE_CHANNEL
        media_content_id = f"{item.number}"
    else:
        media_content_type = item.get("type")
        media_content_id = ""

    title = item["label"]
    can_play = media_content_type in PLAYABLE_MEDIA_TYPES and bool(media_content_id)
    can_expand = media_content_type in EXPANDABLE_MEDIA_TYPES

    thumbnail = item.get("thumbnail")
    if thumbnail:
        thumbnail = media_library.thumbnail_url(thumbnail)

     return BrowseMedia(
        title=title,
        media_content_type=media_content_type,
        media_content_id=media_content_id,
        can_play=can_play,
        can_expand=can_expand,
        thumbnail=thumbnail,
    )


 async def library_payload(media_library):
    """
    Create response payload to describe contents of a specific library.

    Used by async_browse_media.
    """
    library_info = BrowseMedia(
        media_content_id="library",
        media_content_type="library",
        title="Media Library",
        can_play=False,
        can_expand=True,
        children=[],
    )

    library = {
        MEDIA_TYPE_APPS: "Apps",
        MEDIA_TYPE_CHANNELS: "Channels",
    }

    for item in [{"label": n, "type": t} for t, n in library.items()]:
        library_info.children.append(
            item_payload(
                {"label": item["label"], "type": item["type"], "uri": item["type"]},
                media_library,
            )
        )

     return library_info
