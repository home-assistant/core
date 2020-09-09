"""Support for media browsing."""

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_APP,
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_APPS,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_CHANNELS,
)

CONTENT_TYPE_MEDIA_CLASS = {
    MEDIA_TYPE_APP: MEDIA_CLASS_APP,
    MEDIA_TYPE_APPS: MEDIA_CLASS_APP,
    MEDIA_TYPE_CHANNEL: MEDIA_CLASS_CHANNEL,
    MEDIA_TYPE_CHANNELS: MEDIA_CLASS_CHANNEL,
}

PLAYABLE_MEDIA_TYPES = [
    MEDIA_TYPE_APP,
    MEDIA_TYPE_CHANNEL,
]

EXPANDABLE_MEDIA_TYPES = [
    MEDIA_TYPE_APPS,
    MEDIA_TYPE_CHANNELS,
]


def build_item_response(coordinator, payload):
    """Create response payload for the provided media query."""
    search_id = payload["search_id"]
    search_type = payload["search_type"]

    thumbnail = None
    title = None
    media = None

    if search_type == MEDIA_TYPE_APPS:
        title = "Apps"
        media = [
            {"app_id": item.app_id, "title": item.name, "type": MEDIA_TYPE_APP}
            for item in coordinator.data.apps
        ]
    elif search_type == MEDIA_TYPE_CHANNELS:
        title = "Channels"
        media = [
            {
                "channel_number": item.number,
                "title": item.name,
                "type": MEDIA_TYPE_CHANNEL,
            }
            for item in coordinator.data.channels
        ]

    if media is None:
        return None

    return BrowseMedia(
        media_class=CONTENT_TYPE_MEDIA_CLASS[search_type],
        media_content_id=search_id,
        media_content_type=search_type,
        title=title,
        can_play=search_type in PLAYABLE_MEDIA_TYPES and search_id,
        can_expand=True,
        children=[item_payload(item, coordinator) for item in media],
        thumbnail=thumbnail,
    )


def item_payload(item, coordinator):
    """
    Create response payload for a single media item.

    Used by async_browse_media.
    """
    thumbnail = None

    if "app_id" in item:
        media_content_type = MEDIA_TYPE_APP
        media_content_id = item["app_id"]
        thumbnail = coordinator.roku.app_icon_url(item["app_id"])
    elif "channel_number" in item:
        media_content_type = MEDIA_TYPE_CHANNEL
        media_content_id = item["channel_number"]
    else:
        media_content_type = item["type"]
        media_content_id = ""

    title = item["title"]
    can_play = media_content_type in PLAYABLE_MEDIA_TYPES and media_content_id
    can_expand = media_content_type in EXPANDABLE_MEDIA_TYPES

    return BrowseMedia(
        title=title,
        media_class=CONTENT_TYPE_MEDIA_CLASS[media_content_type],
        media_content_type=media_content_type,
        media_content_id=media_content_id,
        can_play=can_play,
        can_expand=can_expand,
        thumbnail=thumbnail,
    )


def library_payload(coordinator):
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
        MEDIA_TYPE_APPS: "Apps",
        MEDIA_TYPE_CHANNELS: "Channels",
    }

    for item in [{"title": name, "type": type_} for type_, name in library.items()]:
        if (
            item["type"] == MEDIA_TYPE_CHANNELS
            and coordinator.data.info.device_type != "tv"
        ):
            continue

        library_info.children.append(
            item_payload(
                {"title": item["title"], "type": item["type"]},
                coordinator,
            )
        )

    return library_info
