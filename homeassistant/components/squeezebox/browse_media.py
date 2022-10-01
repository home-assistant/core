"""Support for media browsing."""
import contextlib

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.helpers.network import is_internal_request

LIBRARY = ["Artists", "Albums", "Tracks", "Playlists", "Genres"]

MEDIA_TYPE_TO_SQUEEZEBOX = {
    "Artists": "artists",
    "Albums": "albums",
    "Tracks": "titles",
    "Playlists": "playlists",
    "Genres": "genres",
    MediaType.ALBUM: "album",
    MediaType.ARTIST: "artist",
    MediaType.TRACK: "title",
    MediaType.PLAYLIST: "playlist",
    MediaType.GENRE: "genre",
}

SQUEEZEBOX_ID_BY_TYPE = {
    MediaType.ALBUM: "album_id",
    MediaType.ARTIST: "artist_id",
    MediaType.TRACK: "track_id",
    MediaType.PLAYLIST: "playlist_id",
    MediaType.GENRE: "genre_id",
}

CONTENT_TYPE_MEDIA_CLASS = {
    "Artists": {"item": MediaClass.DIRECTORY, "children": MediaClass.ARTIST},
    "Albums": {"item": MediaClass.DIRECTORY, "children": MediaClass.ALBUM},
    "Tracks": {"item": MediaClass.DIRECTORY, "children": MediaClass.TRACK},
    "Playlists": {"item": MediaClass.DIRECTORY, "children": MediaClass.PLAYLIST},
    "Genres": {"item": MediaClass.DIRECTORY, "children": MediaClass.GENRE},
    MediaType.ALBUM: {"item": MediaClass.ALBUM, "children": MediaClass.TRACK},
    MediaType.ARTIST: {"item": MediaClass.ARTIST, "children": MediaClass.ALBUM},
    MediaType.TRACK: {"item": MediaClass.TRACK, "children": None},
    MediaType.GENRE: {"item": MediaClass.GENRE, "children": MediaClass.ARTIST},
    MediaType.PLAYLIST: {"item": MediaClass.PLAYLIST, "children": MediaClass.TRACK},
}

CONTENT_TYPE_TO_CHILD_TYPE = {
    MediaType.ALBUM: MediaType.TRACK,
    MediaType.PLAYLIST: MediaType.PLAYLIST,
    MediaType.ARTIST: MediaType.ALBUM,
    MediaType.GENRE: MediaType.ARTIST,
    "Artists": MediaType.ARTIST,
    "Albums": MediaType.ALBUM,
    "Tracks": MediaType.TRACK,
    "Playlists": MediaType.PLAYLIST,
    "Genres": MediaType.GENRE,
}

BROWSE_LIMIT = 1000


async def build_item_response(entity, player, payload):
    """Create response payload for search described by payload."""
    internal_request = is_internal_request(entity.hass)

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
            item_id = str(item["id"])
            item_thumbnail = None

            if artwork_track_id := item.get("artwork_track_id"):
                if internal_request:
                    item_thumbnail = player.generate_image_url_from_track_id(
                        artwork_track_id
                    )
                else:
                    item_thumbnail = entity.get_browse_image_url(
                        item_type, item_id, artwork_track_id
                    )

            children.append(
                BrowseMedia(
                    title=item["title"],
                    media_class=child_media_class["item"],
                    media_content_id=item_id,
                    media_content_type=item_type,
                    can_play=True,
                    can_expand=child_media_class["children"] is not None,
                    thumbnail=item_thumbnail,
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


async def library_payload(hass, player):
    """Create response payload to describe contents of library."""
    library_info = {
        "title": "Music Library",
        "media_class": MediaClass.DIRECTORY,
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
                    thumbnail="https://brands.home-assistant.io/_/squeezebox/logo.png",
                )
            )

    with contextlib.suppress(media_source.BrowseError):
        item = await media_source.async_browse_media(
            hass, None, content_filter=media_source_content_filter
        )
        # If domain is None, it's overview of available sources
        if item.domain is None:
            library_info["children"].extend(item.children)
        else:
            library_info["children"].append(item)

    response = BrowseMedia(**library_info)
    return response


def media_source_content_filter(item: BrowseMedia) -> bool:
    """Content filter for media sources."""
    return item.media_content_type.startswith("audio/")


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
