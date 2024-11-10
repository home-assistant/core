"""Support for media browsing."""

from __future__ import annotations

import contextlib
from typing import Any

from pysqueezebox import Player

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import is_internal_request

LIBRARY = [
    "Favorites",
    "Artists",
    "Albums",
    "Tracks",
    "Playlists",
    "Genres",
    "New Music",
]

MEDIA_TYPE_TO_SQUEEZEBOX = {
    "Favorites": "favorites",
    "Artists": "artists",
    "Albums": "albums",
    "Tracks": "titles",
    "Playlists": "playlists",
    "Genres": "genres",
    "New Music": "new music",
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
    "Favorites": "item_id",
}

CONTENT_TYPE_MEDIA_CLASS: dict[str | MediaType, dict[str, MediaClass | None]] = {
    "Favorites": {"item": MediaClass.DIRECTORY, "children": MediaClass.TRACK},
    "Artists": {"item": MediaClass.DIRECTORY, "children": MediaClass.ARTIST},
    "Albums": {"item": MediaClass.DIRECTORY, "children": MediaClass.ALBUM},
    "Tracks": {"item": MediaClass.DIRECTORY, "children": MediaClass.TRACK},
    "Playlists": {"item": MediaClass.DIRECTORY, "children": MediaClass.PLAYLIST},
    "Genres": {"item": MediaClass.DIRECTORY, "children": MediaClass.GENRE},
    "New Music": {"item": MediaClass.DIRECTORY, "children": MediaClass.ALBUM},
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
    "Favorites": None,  # can only be determined after inspecting the item
    "New Music": MediaType.ALBUM,
}

BROWSE_LIMIT = 1000


async def build_item_response(
    entity: MediaPlayerEntity, player: Player, payload: dict[str, str | None]
) -> BrowseMedia:
    """Create response payload for search described by payload."""

    internal_request = is_internal_request(entity.hass)

    search_id = payload["search_id"]
    search_type = payload["search_type"]
    assert (
        search_type is not None
    )  # async_browse_media will not call this function if search_type is None
    media_class = CONTENT_TYPE_MEDIA_CLASS[search_type]

    children = None

    if search_id and search_id != search_type:
        browse_id = (SQUEEZEBOX_ID_BY_TYPE[search_type], search_id)
    else:
        browse_id = None

    result = await player.async_browse(
        MEDIA_TYPE_TO_SQUEEZEBOX[search_type],
        limit=BROWSE_LIMIT,
        browse_id=browse_id,
    )

    if result is not None and result.get("items"):
        item_type = CONTENT_TYPE_TO_CHILD_TYPE[search_type]

        children = []
        for item in result["items"]:
            item_id = str(item["id"])
            item_thumbnail: str | None = None
            if item_type:
                child_item_type: MediaType | str = item_type
                child_media_class = CONTENT_TYPE_MEDIA_CLASS[item_type]
                can_expand = child_media_class["children"] is not None
                can_play = True

            if search_type == "Favorites":
                if "album_id" in item:
                    item_id = str(item["album_id"])
                    child_item_type = MediaType.ALBUM
                    child_media_class = CONTENT_TYPE_MEDIA_CLASS[MediaType.ALBUM]
                    can_expand = True
                    can_play = True
                elif item["hasitems"]:
                    child_item_type = "Favorites"
                    child_media_class = CONTENT_TYPE_MEDIA_CLASS["Favorites"]
                    can_expand = True
                    can_play = False
                else:
                    child_item_type = "Favorites"
                    child_media_class = CONTENT_TYPE_MEDIA_CLASS[MediaType.TRACK]
                    can_expand = False
                    can_play = True

            if artwork_track_id := item.get("artwork_track_id"):
                if internal_request:
                    item_thumbnail = player.generate_image_url_from_track_id(
                        artwork_track_id
                    )
                elif item_type is not None:
                    item_thumbnail = entity.get_browse_image_url(
                        item_type, item_id, artwork_track_id
                    )
            else:
                item_thumbnail = item.get("image_url")  # will not be proxied by HA

            assert child_media_class["item"] is not None
            children.append(
                BrowseMedia(
                    title=item["title"],
                    media_class=child_media_class["item"],
                    media_content_id=item_id,
                    media_content_type=child_item_type,
                    can_play=can_play,
                    can_expand=can_expand,
                    thumbnail=item_thumbnail,
                )
            )

    if children is None:
        raise BrowseError(f"Media not found: {search_type} / {search_id}")

    assert media_class["item"] is not None
    if not search_id:
        search_id = search_type
    return BrowseMedia(
        title=result.get("title"),
        media_class=media_class["item"],
        children_media_class=media_class["children"],
        media_content_id=search_id,
        media_content_type=search_type,
        can_play=search_type != "Favorites",
        children=children,
        can_expand=True,
    )


async def library_payload(hass: HomeAssistant, player: Player) -> BrowseMedia:
    """Create response payload to describe contents of library."""
    library_info: dict[str, Any] = {
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
            assert media_class["children"] is not None
            library_info["children"].append(
                BrowseMedia(
                    title=item,
                    media_class=media_class["children"],
                    media_content_id=item,
                    media_content_type=item,
                    can_play=item != "Favorites",
                    can_expand=True,
                )
            )

    with contextlib.suppress(media_source.BrowseError):
        browse = await media_source.async_browse_media(
            hass, None, content_filter=media_source_content_filter
        )
        # If domain is None, it's overview of available sources
        if browse.domain is None:
            library_info["children"].extend(browse.children)
        else:
            library_info["children"].append(browse)

    return BrowseMedia(**library_info)


def media_source_content_filter(item: BrowseMedia) -> bool:
    """Content filter for media sources."""
    return item.media_content_type.startswith("audio/")


async def generate_playlist(player: Player, payload: dict[str, str]) -> list | None:
    """Generate playlist from browsing payload."""
    media_type = payload["search_type"]
    media_id = payload["search_id"]

    if media_type not in SQUEEZEBOX_ID_BY_TYPE:
        raise BrowseError(f"Media type not supported: {media_type}")

    browse_id = (SQUEEZEBOX_ID_BY_TYPE[media_type], media_id)
    result = await player.async_browse(
        "titles", limit=BROWSE_LIMIT, browse_id=browse_id
    )
    if result and "items" in result:
        items: list = result["items"]
        return items
    raise BrowseError(f"Media not found: {media_type} / {media_id}")
