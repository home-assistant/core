"""Support for media browsing."""
import json

from homeassistant.components.media_player import BrowseError, BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_GENRE,
    MEDIA_CLASS_PLAYLIST,
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

NON_EXPANDABLE_ITEM_TYPES = [
    "song",
    "webradio",
    "mywebradio",
    "cuesong",
    "album",
    "artist",
    "cd",
    "play-playlist",
]

PLAYLISTS_URI_PREFIX = "playlists"
ARTISTS_URI_PREFIX = "artists://"
ALBUMS_URI_PREFIX = "albums://"
GENRES_URI_PREFIX = "genres://"
RADIO_URI_PREFIX = "radio"
LAST_100_URI_PREFIX = "Last_100"
FAVOURITES_URI = "favourites"


def _item_to_children_media_class(item, info=None):
    if info and "album" in info and "artist" in info:
        return MEDIA_CLASS_TRACK
    if item["uri"].startswith(PLAYLISTS_URI_PREFIX):
        return MEDIA_CLASS_PLAYLIST
    if item["uri"].startswith(ARTISTS_URI_PREFIX):
        if len(item["uri"]) > len(ARTISTS_URI_PREFIX):
            return MEDIA_CLASS_ALBUM
        return MEDIA_CLASS_ARTIST
    if item["uri"].startswith(ALBUMS_URI_PREFIX):
        if len(item["uri"]) > len(ALBUMS_URI_PREFIX):
            return MEDIA_CLASS_TRACK
        return MEDIA_CLASS_ALBUM
    if item["uri"].startswith(GENRES_URI_PREFIX):
        if len(item["uri"]) > len(GENRES_URI_PREFIX):
            return MEDIA_CLASS_ALBUM
        return MEDIA_CLASS_GENRE
    if item["uri"].startswith(LAST_100_URI_PREFIX) or item["uri"] == FAVOURITES_URI:
        return MEDIA_CLASS_TRACK
    if item["uri"].startswith(RADIO_URI_PREFIX):
        return MEDIA_CLASS_CHANNEL
    return MEDIA_CLASS_DIRECTORY


def _item_to_media_class(item, parent_item=None):
    if "type" not in item:
        return MEDIA_CLASS_DIRECTORY
    if item["type"] in ("webradio", "mywebradio"):
        return MEDIA_CLASS_CHANNEL
    if item["type"] in ("song", "cuesong"):
        return MEDIA_CLASS_TRACK
    if item.get("artist"):
        return MEDIA_CLASS_ALBUM
    if item["uri"].startswith(ARTISTS_URI_PREFIX) and len(item["uri"]) > len(
        ARTISTS_URI_PREFIX
    ):
        return MEDIA_CLASS_ARTIST
    if parent_item:
        return _item_to_children_media_class(parent_item)
    return MEDIA_CLASS_DIRECTORY


def _list_payload(item, children=None):
    return BrowseMedia(
        title=item["name"],
        media_class=MEDIA_CLASS_DIRECTORY,
        children_media_class=_item_to_children_media_class(item),
        media_content_type=MEDIA_TYPE_MUSIC,
        media_content_id=json.dumps(item),
        can_play=False,
        can_expand=True,
    )


def _raw_item_payload(entity, item, parent_item=None, title=None, info=None):
    if "type" in item:
        if thumbnail := item.get("albumart"):
            item_hash = str(hash(thumbnail))
            entity.thumbnail_cache.setdefault(item_hash, thumbnail)
            thumbnail = entity.get_browse_image_url(MEDIA_TYPE_MUSIC, item_hash)
    else:
        # don't use the built-in volumio white-on-white icons
        thumbnail = None

    return {
        "title": title or item.get("title"),
        "media_class": _item_to_media_class(item, parent_item),
        "children_media_class": _item_to_children_media_class(item, info),
        "media_content_type": MEDIA_TYPE_MUSIC,
        "media_content_id": json.dumps(item),
        "can_play": item.get("type") in PLAYABLE_ITEM_TYPES,
        "can_expand": item.get("type") not in NON_EXPANDABLE_ITEM_TYPES,
        "thumbnail": thumbnail,
    }


def _item_payload(entity, item, parent_item):
    return BrowseMedia(**_raw_item_payload(entity, item, parent_item=parent_item))


async def browse_top_level(media_library):
    """Browse the top-level of a Volumio media hierarchy."""
    navigation = await media_library.browse()
    children = [_list_payload(item) for item in navigation["lists"]]
    return BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        title="Media Library",
        can_play=False,
        can_expand=True,
        children=children,
    )


async def browse_node(entity, media_library, media_content_type, media_content_id):
    """Browse a node of a Volumio media hierarchy."""
    json_item = json.loads(media_content_id)
    navigation = await media_library.browse(json_item["uri"])
    if "lists" not in navigation:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")

    # we only use the first list since the second one could include all tracks
    first_list = navigation["lists"][0]
    children = [
        _item_payload(entity, item, parent_item=json_item)
        for item in first_list["items"]
    ]
    info = navigation.get("info")
    if not (title := first_list.get("title")):
        if info:
            title = f"{info.get('album')} ({info.get('artist')})"
        else:
            title = "Media Library"

    payload = _raw_item_payload(entity, json_item, title=title, info=info)
    return BrowseMedia(**payload, children=children)
