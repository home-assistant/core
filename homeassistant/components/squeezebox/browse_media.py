"""Support for media browsing."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
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

from .const import UNPLAYABLE_TYPES

LIBRARY = [
    "Favorites",
    "Artists",
    "Albums",
    "Tracks",
    "Playlists",
    "Genres",
    "New Music",
    "Apps",
    "Radios",
]

MEDIA_TYPE_TO_SQUEEZEBOX: dict[str | MediaType, str] = {
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
    "Apps": "apps",
    "Radios": "radios",
}

SQUEEZEBOX_ID_BY_TYPE: dict[str | MediaType, str] = {
    MediaType.ALBUM: "album_id",
    MediaType.ARTIST: "artist_id",
    MediaType.TRACK: "track_id",
    MediaType.PLAYLIST: "playlist_id",
    MediaType.GENRE: "genre_id",
    "Favorites": "item_id",
    MediaType.APPS: "item_id",
}

CONTENT_TYPE_MEDIA_CLASS: dict[str | MediaType, dict[str, MediaClass | None]] = {
    "Favorites": {"item": MediaClass.DIRECTORY, "children": MediaClass.TRACK},
    "Apps": {"item": MediaClass.DIRECTORY, "children": MediaClass.APP},
    "Radios": {"item": MediaClass.DIRECTORY, "children": MediaClass.APP},
    "App": {"item": MediaClass.DIRECTORY, "children": MediaClass.TRACK},
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
    MediaType.APP: {"item": MediaClass.DIRECTORY, "children": MediaClass.TRACK},
    MediaType.APPS: {"item": MediaClass.DIRECTORY, "children": MediaClass.APP},
}

CONTENT_TYPE_TO_CHILD_TYPE: dict[
    str | MediaType,
    str | MediaType | None,
] = {
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
    "Apps": MediaClass.APP,
    "Radios": MediaClass.APP,
    "App": None,  # can only be determined after inspecting the item
    "New Music": MediaType.ALBUM,
    MediaType.APPS: MediaType.APP,
    MediaType.APP: MediaType.TRACK,
}


@dataclass
class Squeezebox_maps:
    """Class for browser to squeezebox mappings."""

    content_type_to_child_type: dict[
        str | MediaType,
        str | MediaType | None,
    ]
    content_type_media_class: dict[str | MediaType, dict[str, MediaClass | None]]
    squeezebox_id_by_type: dict[str | MediaType, str]
    media_type_to_squeezebox: dict[str | MediaType, str]


async def build_item_response(
    entity: MediaPlayerEntity,
    player: Player,
    payload: dict[str, str | None],
    browse_limit: int,
    known_apps: set[str],
    squeezebox_maps: Squeezebox_maps,
) -> BrowseMedia:
    """Create response payload for search described by payload."""

    def update_squeezebox_maps(cmd: str | MediaType, type: str) -> None:
        """Add items to maps for new apps or radios."""
        squeezebox_maps.media_type_to_squeezebox.update({cmd: cmd})
        squeezebox_maps.squeezebox_id_by_type.update({cmd: type})
        squeezebox_maps.content_type_media_class.update(
            {
                cmd: {
                    "item": MediaClass.DIRECTORY,
                    "children": MediaClass.TRACK,
                }
            }
        )
        squeezebox_maps.content_type_to_child_type.update({cmd: MediaType.TRACK})

    def build_response_apps_radios_category(
        _cmd: str | MediaType,
    ) -> tuple[str | MediaType, dict[str, MediaClass | None], bool, bool]:
        """Build item for App or radio category."""
        _child_item_type: str | MediaType = _cmd
        _child_media_class: dict[str, MediaClass | None] = (
            squeezebox_maps.content_type_media_class[_cmd]
        )
        _can_expand: bool = True
        _can_play: bool = False
        return (_child_item_type, _child_media_class, _can_expand, _can_play)

    def build_response_known_app(
        search_type: str, item: dict[str, Any]
    ) -> tuple[str | MediaType, dict[str, MediaClass | None], bool, bool]:
        """Build item for app or radio."""
        _child_item_type: str | MediaType = search_type
        _child_media_class: dict[str, MediaClass | None] = (
            squeezebox_maps.content_type_media_class[search_type]
        )
        _can_play: bool = bool(item["isaudio"] and item.get("url"))
        _can_expand: bool = item["hasitems"]
        return (_child_item_type, _child_media_class, _can_expand, _can_play)

    def build_response_favorite(
        item_id: str, item: dict[str, Any]
    ) -> tuple[str | MediaType, dict[str, MediaClass | None], bool, bool, str]:
        """Build item for favorite."""
        _item_id: str = item_id
        _child_item_type: str | MediaType
        _child_media_class: dict[str, MediaClass | None]
        _can_play: bool
        _can_expand: bool
        if "album_id" in item:
            _item_id = str(item["album_id"])
            _child_item_type = MediaType.ALBUM
            _child_media_class = squeezebox_maps.content_type_media_class[
                MediaType.ALBUM
            ]
            _can_expand = True
            _can_play = True
        elif item["hasitems"] and not item["isaudio"]:
            _child_item_type = "Favorites"
            _child_media_class = squeezebox_maps.content_type_media_class["Favorites"]
            _can_expand = True
            _can_play = False
        else:
            _child_item_type = "Favorites"
            _child_media_class = squeezebox_maps.content_type_media_class[
                MediaType.TRACK
            ]
            _can_expand = item["hasitems"]
            _can_play = bool(item["isaudio"] and item.get("url"))
        return (
            _child_item_type,
            _child_media_class,
            _can_expand,
            _can_play,
            _item_id,
        )

    def get_thumbnail(
        search_type: str,
        item: dict[str, Any],
        item_type: str | MediaType | None,
        item_id: str,
        internal_request: bool,
        entity: MediaPlayerEntity,
    ) -> str | None:
        _item_thumbnail: str | None = None
        if artwork_track_id := item.get("artwork_track_id"):
            if internal_request:
                _item_thumbnail = player.generate_image_url_from_track_id(
                    artwork_track_id
                )
            elif item_type is not None:
                _item_thumbnail = entity.get_browse_image_url(
                    item_type, item_id, artwork_track_id
                )
        elif search_type in ["Apps", "Radios"]:
            _item_thumbnail = player.generate_image_url(item["icon"])
        else:
            _item_thumbnail = item.get("image_url")  # will not be proxied by HA
        return _item_thumbnail

    internal_request = is_internal_request(entity.hass)

    search_id = payload["search_id"]
    search_type = payload["search_type"]
    assert (
        search_type is not None
    )  # async_browse_media will not call this function if search_type is None
    media_class = squeezebox_maps.content_type_media_class[search_type]

    children = None

    if search_id and search_id != search_type:
        browse_id = (squeezebox_maps.squeezebox_id_by_type[search_type], search_id)
    else:
        browse_id = None

    result = await player.async_browse(
        squeezebox_maps.media_type_to_squeezebox[search_type],
        limit=browse_limit,
        browse_id=browse_id,
    )

    if result is not None and result.get("items"):
        item_type = squeezebox_maps.content_type_to_child_type[search_type]

        children = []
        list_playable = []
        for item in result["items"]:
            item_id = str(item.get("id", ""))
            item_thumbnail: str | None = None

            if search_type in ["Apps", "Radios"]:
                # item["cmd"] contains the name of the command to use with the cli for the app
                # add the command to the dictionaries
                if item["title"] == "Search" or item.get("type") in UNPLAYABLE_TYPES:
                    # Skip searches in apps as they'd need UI or if the link isn't to audio
                    continue
                _cmd = "app-" + item["cmd"]

                if _cmd not in known_apps:
                    known_apps.add(_cmd)

                update_squeezebox_maps(_cmd, "item_id")

                child_item_type, child_media_class, can_expand, can_play = (
                    build_response_apps_radios_category(_cmd)
                )

            elif search_type in known_apps:
                if (
                    item.get("title") in ["Search", None]
                    or item.get("type") in UNPLAYABLE_TYPES
                ):
                    # Skip searches in apps as they'd need UI
                    continue

                child_item_type, child_media_class, can_expand, can_play = (
                    build_response_known_app(search_type, item)
                )
            elif search_type == "Favorites":
                child_item_type, child_media_class, can_expand, can_play, item_id = (
                    build_response_favorite(item_id, item)
                )
            elif item_type:
                child_item_type = item_type
                child_media_class = squeezebox_maps.content_type_media_class[item_type]
                can_expand = child_media_class["children"] is not None
                can_play = True

            item_thumbnail = get_thumbnail(
                search_type, item, item_type, item_id, internal_request, entity
            )

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
            list_playable.append(can_play)

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
        can_play=any(list_playable),
        children=children,
        can_expand=True,
    )


async def library_payload(
    hass: HomeAssistant,
    player: Player,
    squeezebox_maps: Squeezebox_maps,
) -> BrowseMedia:
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
        media_class = squeezebox_maps.content_type_media_class[item]

        result = await player.async_browse(
            squeezebox_maps.media_type_to_squeezebox[item],
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
                    can_play=item not in ["Favorites", "Apps", "Radios"],
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


async def generate_playlist(
    player: Player,
    payload: dict[str, str],
    browse_limit: int,
    squeezebox_maps: Squeezebox_maps,
) -> list | None:
    """Generate playlist from browsing payload."""
    media_type = payload["search_type"]
    media_id = payload["search_id"]

    if media_type not in squeezebox_maps.squeezebox_id_by_type:
        raise BrowseError(f"Media type not supported: {media_type}")

    browse_id = (squeezebox_maps.squeezebox_id_by_type[media_type], media_id)
    if media_type[:4] == "app-":
        category = media_type
    else:
        category = "titles"

    result = await player.async_browse(
        category, limit=browse_limit, browse_id=browse_id
    )
    if result and "items" in result:
        items: list = result["items"]
        return items
    raise BrowseError(f"Media not found: {media_type} / {media_id}")
