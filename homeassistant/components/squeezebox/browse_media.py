"""Support for media browsing."""
from homeassistant.components.media_player import BrowseError, BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_GENRE,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_TRACK,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_GENRE,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_TRACK,
)

LIBRARY = ["Artists", "Albums", "Tracks", "Playlists", "Genres"]

MEDIA_TYPE_TO_SQUEEZEBOX = {
    "Artists": "artists",
    "Albums": "albums",
    "Tracks": "titles",
    "Playlists": "playlists",
    "Genres": "genres",
    MEDIA_TYPE_ALBUM: "album",
    MEDIA_TYPE_ARTIST: "artist",
    MEDIA_TYPE_TRACK: "title",
    MEDIA_TYPE_PLAYLIST: "playlist",
    MEDIA_TYPE_GENRE: "genre",
}

SQUEEZEBOX_ID_BY_TYPE = {
    MEDIA_TYPE_ALBUM: "album_id",
    MEDIA_TYPE_ARTIST: "artist_id",
    MEDIA_TYPE_TRACK: "track_id",
    MEDIA_TYPE_PLAYLIST: "playlist_id",
    MEDIA_TYPE_GENRE: "genre_id",
}

CONTENT_TYPE_MEDIA_CLASS = {
    "Artists": {"item": MEDIA_CLASS_DIRECTORY, "children": MEDIA_CLASS_ARTIST},
    "Albums": {"item": MEDIA_CLASS_DIRECTORY, "children": MEDIA_CLASS_ALBUM},
    "Tracks": {"item": MEDIA_CLASS_DIRECTORY, "children": MEDIA_CLASS_TRACK},
    "Playlists": {"item": MEDIA_CLASS_DIRECTORY, "children": MEDIA_CLASS_PLAYLIST},
    "Genres": {"item": MEDIA_CLASS_DIRECTORY, "children": MEDIA_CLASS_GENRE},
    MEDIA_TYPE_ALBUM: {"item": MEDIA_CLASS_ALBUM, "children": MEDIA_CLASS_TRACK},
    MEDIA_TYPE_ARTIST: {"item": MEDIA_CLASS_ARTIST, "children": MEDIA_CLASS_ALBUM},
    MEDIA_TYPE_TRACK: {"item": MEDIA_CLASS_TRACK, "children": None},
    MEDIA_TYPE_GENRE: {"item": MEDIA_CLASS_GENRE, "children": MEDIA_CLASS_ARTIST},
    MEDIA_TYPE_PLAYLIST: {
        "item": MEDIA_CLASS_PLAYLIST,
        "children": MEDIA_CLASS_TRACK,
    },
}

CONTENT_TYPE_TO_CHILD_TYPE = {
    MEDIA_TYPE_ALBUM: MEDIA_TYPE_TRACK,
    MEDIA_TYPE_PLAYLIST: MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_ARTIST: MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_GENRE: MEDIA_TYPE_ARTIST,
    "Artists": MEDIA_TYPE_ARTIST,
    "Albums": MEDIA_TYPE_ALBUM,
    "Tracks": MEDIA_TYPE_TRACK,
    "Playlists": MEDIA_TYPE_PLAYLIST,
    "Genres": MEDIA_TYPE_GENRE,
}

BROWSE_LIMIT = 1000


async def build_item_response(player, payload):
    """Create response payload for search described by payload."""
    search_id = payload["search_id"]
    search_type = payload["search_type"]

    media_class = CONTENT_TYPE_MEDIA_CLASS[search_type]

    if search_id and search_id != search_type:
        browse_id = (SQUEEZEBOX_ID_BY_TYPE[search_type], search_id)
    else:
        browse_id = None

    result = await player.async_browse(
        MEDIA_TYPE_TO_SQUEEZEBOX[search_type],
        limit=BROWSE_LIMIT,
        browse_id=browse_id,
    )

    children = None

    if result is not None and result.get("items"):
        item_type = CONTENT_TYPE_TO_CHILD_TYPE[search_type]
        child_media_class = CONTENT_TYPE_MEDIA_CLASS[item_type]

        children = []
        for item in result["items"]:
            children.append(
                BrowseMedia(
                    title=item["title"],
                    media_class=child_media_class["item"],
                    media_content_id=str(item["id"]),
                    media_content_type=item_type,
                    can_play=True,
                    can_expand=child_media_class["children"] is not None,
                    thumbnail=item.get("image_url"),
                )
            )

    if children is None:
        raise BrowseError(f"Media not found: {search_type} / {search_id}")

    return BrowseMedia(
        title=result.get("title"),
        media_class=media_class["item"],
        children_media_class=media_class["children"],
        media_content_id=search_id,
        media_content_type=search_type,
        can_play=True,
        children=children,
        can_expand=True,
    )


async def library_payload(player):
    """Create response payload to describe contents of library."""

    library_info = {
        "title": "Music Library",
        "media_class": MEDIA_CLASS_DIRECTORY,
        "media_content_id": "library",
        "media_content_type": "library",
        "can_play": False,
        "can_expand": True,
        "children": [],
    }

    for item in LIBRARY:
        media_class = CONTENT_TYPE_MEDIA_CLASS[item]
        result = await player.async_browse(
            MEDIA_TYPE_TO_SQUEEZEBOX[item],
            limit=1,
        )
        if result is not None and result.get("items") is not None:
            library_info["children"].append(
                BrowseMedia(
                    title=item,
                    media_class=media_class["children"],
                    media_content_id=item,
                    media_content_type=item,
                    can_play=True,
                    can_expand=True,
                )
            )

    response = BrowseMedia(**library_info)
    return response


async def generate_playlist(player, payload):
    """Generate playlist from browsing payload."""
    media_type = payload["search_type"]
    media_id = payload["search_id"]

    if media_type not in SQUEEZEBOX_ID_BY_TYPE:
        return None

    browse_id = (SQUEEZEBOX_ID_BY_TYPE[media_type], media_id)
    result = await player.async_browse(
        "titles", limit=BROWSE_LIMIT, browse_id=browse_id
    )
    return result.get("items")
