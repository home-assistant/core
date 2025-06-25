"""Support for media browsing."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
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

from .const import DOMAIN, UNPLAYABLE_TYPES

LIBRARY = [
    "favorites",
    "artists",
    "albums",
    "tracks",
    "playlists",
    "genres",
    "new music",
    "album artists",
    "apps",
    "radios",
]

MEDIA_TYPE_TO_SQUEEZEBOX: dict[str | MediaType, str] = {
    "favorites": "favorites",
    "artists": "artists",
    "albums": "albums",
    "tracks": "titles",
    "playlists": "playlists",
    "genres": "genres",
    "new music": "new music",
    "album artists": "album artists",
    MediaType.ALBUM: "album",
    MediaType.ARTIST: "artist",
    MediaType.TRACK: "title",
    MediaType.PLAYLIST: "playlist",
    MediaType.GENRE: "genre",
    MediaType.APPS: "apps",
    "radios": "radios",
    "favorite": "favorite",
}

SQUEEZEBOX_ID_BY_TYPE: dict[str | MediaType, str] = {
    MediaType.ALBUM: "album_id",
    "albums": "album_id",
    MediaType.ARTIST: "artist_id",
    "artists": "artist_id",
    MediaType.TRACK: "track_id",
    "tracks": "track_id",
    MediaType.PLAYLIST: "playlist_id",
    "playlists": "playlist_id",
    MediaType.GENRE: "genre_id",
    "genres": "genre_id",
    "favorite": "item_id",
    "favorites": "item_id",
    MediaType.APPS: "item_id",
    "app": "item_id",
    "radios": "item_id",
    "radio": "item_id",
}

CONTENT_TYPE_MEDIA_CLASS: dict[str | MediaType, dict[str, MediaClass | str]] = {
    "favorites": {"item": MediaClass.DIRECTORY, "children": MediaClass.TRACK},
    "favorite": {"item": "favorite", "children": ""},
    "radios": {"item": MediaClass.DIRECTORY, "children": MediaClass.APP},
    "radio": {"item": MediaClass.DIRECTORY, "children": MediaClass.APP},
    "artists": {"item": MediaClass.DIRECTORY, "children": MediaClass.ARTIST},
    "albums": {"item": MediaClass.DIRECTORY, "children": MediaClass.ALBUM},
    "tracks": {"item": MediaClass.DIRECTORY, "children": MediaClass.TRACK},
    "playlists": {"item": MediaClass.DIRECTORY, "children": MediaClass.PLAYLIST},
    "genres": {"item": MediaClass.DIRECTORY, "children": MediaClass.GENRE},
    "new music": {"item": MediaClass.DIRECTORY, "children": MediaClass.ALBUM},
    "album artists": {"item": MediaClass.DIRECTORY, "children": MediaClass.ARTIST},
    MediaType.ALBUM: {"item": MediaClass.ALBUM, "children": MediaClass.TRACK},
    MediaType.ARTIST: {"item": MediaClass.ARTIST, "children": MediaClass.ALBUM},
    MediaType.TRACK: {"item": MediaClass.TRACK, "children": ""},
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
    "artists": MediaType.ARTIST,
    "albums": MediaType.ALBUM,
    "tracks": MediaType.TRACK,
    "playlists": MediaType.PLAYLIST,
    "genres": MediaType.GENRE,
    "favorites": None,  # can only be determined after inspecting the item
    "radios": MediaClass.APP,
    "new music": MediaType.ALBUM,
    "album artists": MediaType.ARTIST,
    MediaType.APPS: MediaType.APP,
    MediaType.APP: MediaType.TRACK,
    "favorite": None,
}


@dataclass
class BrowseData:
    """Class for browser to squeezebox mappings and other browse data."""

    content_type_to_child_type: dict[
        str | MediaType,
        str | MediaType | None,
    ] = field(default_factory=dict)
    content_type_media_class: dict[str | MediaType, dict[str, MediaClass | str]] = (
        field(default_factory=dict)
    )
    squeezebox_id_by_type: dict[str | MediaType, str] = field(default_factory=dict)
    media_type_to_squeezebox: dict[str | MediaType, str] = field(default_factory=dict)
    known_apps_radios: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Initialise the maps."""
        self.content_type_media_class.update(CONTENT_TYPE_MEDIA_CLASS)
        self.content_type_to_child_type.update(CONTENT_TYPE_TO_CHILD_TYPE)
        self.squeezebox_id_by_type.update(SQUEEZEBOX_ID_BY_TYPE)
        self.media_type_to_squeezebox.update(MEDIA_TYPE_TO_SQUEEZEBOX)


def _add_new_command_to_browse_data(
    browse_data: BrowseData, cmd: str | MediaType, type: str
) -> None:
    """Add items to maps for new apps or radios."""
    browse_data.media_type_to_squeezebox[cmd] = cmd
    browse_data.squeezebox_id_by_type[cmd] = type
    browse_data.content_type_media_class[cmd] = {
        "item": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    }
    browse_data.content_type_to_child_type[cmd] = MediaType.TRACK


def _build_response_apps_radios_category(
    browse_data: BrowseData, cmd: str | MediaType, item: dict[str, Any]
) -> BrowseMedia:
    """Build item for App or radio category."""
    return BrowseMedia(
        media_content_id=item["id"],
        title=item["title"],
        media_content_type=cmd,
        media_class=browse_data.content_type_media_class[cmd]["item"],
        can_expand=True,
        can_play=False,
    )


def _build_response_known_app(
    browse_data: BrowseData, search_type: str, item: dict[str, Any]
) -> BrowseMedia:
    """Build item for app or radio."""

    return BrowseMedia(
        media_content_id=item["id"],
        title=item["title"],
        media_content_type=search_type,
        media_class=browse_data.content_type_media_class[search_type]["item"],
        can_play=bool(item["isaudio"] and item.get("url")),
        can_expand=item["hasitems"],
    )


def _build_response_favorites(item: dict[str, Any]) -> BrowseMedia:
    """Build item for favorites."""
    if "album_id" in item:
        return BrowseMedia(
            media_content_id=str(item["album_id"]),
            title=item["title"],
            media_content_type=MediaType.ALBUM,
            media_class=CONTENT_TYPE_MEDIA_CLASS[MediaType.ALBUM]["item"],
            can_expand=True,
            can_play=True,
        )
    if item.get("hasitems") and not item.get("isaudio"):
        return BrowseMedia(
            media_content_id=item["id"],
            title=item["title"],
            media_content_type="favorites",
            media_class=CONTENT_TYPE_MEDIA_CLASS["favorites"]["item"],
            can_expand=True,
            can_play=False,
        )
    return BrowseMedia(
        media_content_id=item["id"],
        title=item["title"],
        media_content_type="favorite",
        media_class=CONTENT_TYPE_MEDIA_CLASS[MediaType.TRACK]["item"],
        can_expand=bool(item.get("hasitems")),
        can_play=bool(item["isaudio"] and item.get("url")),
    )


def _get_item_thumbnail(
    item: dict[str, Any],
    player: Player,
    entity: MediaPlayerEntity,
    item_type: str | MediaType | None,
    search_type: str,
    internal_request: bool,
) -> str | None:
    """Construct path to thumbnail image."""
    item_thumbnail: str | None = None
    if artwork_track_id := item.get("artwork_track_id"):
        if internal_request:
            item_thumbnail = player.generate_image_url_from_track_id(artwork_track_id)
        elif item_type is not None:
            item_thumbnail = entity.get_browse_image_url(
                item_type, item["id"], artwork_track_id
            )

    elif search_type in ["apps", "radios"]:
        item_thumbnail = player.generate_image_url(item["icon"])
    if item_thumbnail is None:
        item_thumbnail = item.get("image_url")  # will not be proxied by HA
    return item_thumbnail


async def build_item_response(
    entity: MediaPlayerEntity,
    player: Player,
    payload: dict[str, str | None],
    browse_limit: int,
    browse_data: BrowseData,
) -> BrowseMedia:
    """Create response payload for search described by payload."""

    internal_request = is_internal_request(entity.hass)

    search_id = payload["search_id"]
    search_type = payload["search_type"]
    search_query = payload.get("search_query")
    assert (
        search_type is not None
    )  # async_browse_media will not call this function if search_type is None
    media_class = browse_data.content_type_media_class[search_type]

    children = None

    if search_id and search_id != search_type:
        browse_id = (browse_data.squeezebox_id_by_type[search_type], search_id)
    else:
        browse_id = None

    result = await player.async_browse(
        browse_data.media_type_to_squeezebox[search_type],
        limit=browse_limit,
        browse_id=browse_id,
        search_query=search_query,
    )

    if result is not None and result.get("items"):
        item_type = browse_data.content_type_to_child_type[search_type]

        children = []
        for item in result["items"]:
            # Force the item id to a string in case it's numeric from some lms
            item["id"] = str(item.get("id", ""))
            if search_type in ["favorites", "favorite"]:
                child_media = _build_response_favorites(item)

            elif search_type in ["apps", "radios"]:
                # item["cmd"] contains the name of the command to use with the cli for the app
                # add the command to the dictionaries
                if item["title"] == "Search" or item.get("type") in UNPLAYABLE_TYPES:
                    # Skip searches in apps as they'd need UI or if the link isn't to audio
                    continue
                app_cmd = "app-" + item["cmd"]

                if app_cmd not in browse_data.known_apps_radios:
                    browse_data.known_apps_radios.add(app_cmd)
                    _add_new_command_to_browse_data(browse_data, app_cmd, "item_id")

                child_media = _build_response_apps_radios_category(
                    browse_data=browse_data, cmd=app_cmd, item=item
                )

            elif search_type in browse_data.known_apps_radios:
                if (
                    item.get("title") in ["Search", None]
                    or item.get("type") in UNPLAYABLE_TYPES
                ):
                    # Skip searches in apps as they'd need UI
                    continue

                child_media = _build_response_known_app(browse_data, search_type, item)

            elif item_type:
                child_media = BrowseMedia(
                    media_content_id=item["id"],
                    title=item["title"],
                    media_content_type=item_type,
                    media_class=CONTENT_TYPE_MEDIA_CLASS[item_type]["item"],
                    can_expand=CONTENT_TYPE_MEDIA_CLASS[item_type]["children"]
                    is not None,
                    can_play=True,
                )

            assert child_media.media_class is not None

            child_media.thumbnail = _get_item_thumbnail(
                item=item,
                player=player,
                entity=entity,
                item_type=item_type,
                search_type=search_type,
                internal_request=internal_request,
            )

            children.append(child_media)

    if children is None:
        raise BrowseError(
            translation_domain=DOMAIN,
            translation_key="browse_media_not_found",
            translation_placeholders={
                "type": str(search_type),
                "id": str(search_id),
            },
        )

    assert media_class["item"] is not None
    if not search_id:
        search_id = search_type

    return BrowseMedia(
        title=result.get("title"),
        media_class=media_class["item"],
        children_media_class=media_class["children"],
        media_content_id=search_id,
        media_content_type=search_type,
        can_play=any(child.can_play for child in children),
        children=children,
        can_expand=True,
    )


async def library_payload(
    hass: HomeAssistant,
    player: Player,
    browse_media: BrowseData,
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
        media_class = browse_media.content_type_media_class[item]

        result = await player.async_browse(
            browse_media.media_type_to_squeezebox[item],
            limit=1,
        )
        if result is not None and result.get("items") is not None:
            assert media_class["children"] is not None
            library_info["children"].append(
                BrowseMedia(
                    title=item.title(),
                    media_class=media_class["children"],
                    media_content_id=item,
                    media_content_type=item,
                    can_play=item not in ["favorites", "apps", "radios"],
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
    browse_media: BrowseData,
) -> list | None:
    """Generate playlist from browsing payload."""
    media_type = payload["search_type"]
    media_id = payload["search_id"]

    if media_type not in browse_media.squeezebox_id_by_type:
        raise BrowseError(
            translation_domain=DOMAIN,
            translation_key="browse_media_type_not_supported",
            translation_placeholders={
                "media_type": str(media_type),
            },
        )

    browse_id = (browse_media.squeezebox_id_by_type[media_type], media_id)
    if media_type.startswith("app-"):
        category = media_type
    else:
        category = "titles"

    result = await player.async_browse(
        category, limit=browse_limit, browse_id=browse_id
    )
    if result and "items" in result:
        items: list = result["items"]
        return items
    raise BrowseError(
        translation_domain=DOMAIN,
        translation_key="browse_media_not_found",
        translation_placeholders={
            "type": str(media_type),
            "id": str(media_id),
        },
    )
