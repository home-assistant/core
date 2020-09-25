"""Support for media browsing."""
import json

from homeassistant.components.media_player import BrowseError, BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_TRACK,
    MEDIA_TYPE_MUSIC,
)

PLAYABLE_ITEM_TYPES = [
    "folder",
    "song",
    "mywebradio",
    "webradio",
    "playlist",
    "cuesong",
    "remdisk",
    "cuefile",
    "folder-with-favourites",
    "internal-folder",
]

NON_EXAPNDABLE_ITEM_TYPES = [
    "song",
    "webradio",
    "mywebradio",
    "cuesong",
    "album",
    "artist",
    "cd",
    "play-playlist",
]


def _item_to_media_class(item):
    if item["type"] in ["webradio", "mywebradio"]:
        return MEDIA_CLASS_CHANNEL
    if item["type"] in ["song", "cuesong"]:
        return MEDIA_CLASS_TRACK
    return MEDIA_CLASS_DIRECTORY


def _list_payload(media_library, item):
    return BrowseMedia(
        title=item["name"],
        media_class=MEDIA_CLASS_DIRECTORY,
        children_media_class=MEDIA_CLASS_MUSIC,
        media_content_type=MEDIA_TYPE_MUSIC,
        media_content_id=json.dumps(item),
        can_play=False,
        can_expand=True,
        thumbnail=media_library.canonic_url(item["albumart"]),
    )


def _item_payload(media_library, item):
    thumbnail = item.get("albumart")
    if thumbnail:
        thumbnail = media_library.canonic_url(thumbnail)
    return BrowseMedia(
        title=item["title"],
        media_class=_item_to_media_class(item),
        children_media_class=MEDIA_CLASS_MUSIC,
        media_content_type=MEDIA_TYPE_MUSIC,
        media_content_id=json.dumps(item),
        can_play=item["type"] in PLAYABLE_ITEM_TYPES,
        can_expand=item["type"] not in NON_EXAPNDABLE_ITEM_TYPES,
        thumbnail=thumbnail,
    )


async def browse_top_level(media_library):
    """Browse the top-level of a Volumio media hierarchy."""
    navigation = await media_library.browse()
    children = [_list_payload(media_library, item) for item in navigation["lists"]]
    return BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        title="Media Library",
        can_play=False,
        can_expand=True,
        children=children,
    )


async def browse_node(media_library, media_content_type, media_content_id):
    """Browse a node of a Volumio media hierarchy."""
    navigation = await media_library.browse(json.loads(media_content_id)["uri"])
    if "lists" not in navigation:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")

    # we only use the first list since the second one could include all tracks
    first_list = navigation["lists"][0]
    children = [_item_payload(media_library, item) for item in first_list["items"]]
    title = first_list.get("title")
    if not title:
        info = navigation.get("info")
        if info:
            title = f"{info['album']} ({info['artist']})"
        else:
            title = "Media Library"

    return BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id=media_content_id,
        media_content_type=media_content_type,
        title=title,
        can_play=False,
        can_expand=True,
        children=children,
    )
