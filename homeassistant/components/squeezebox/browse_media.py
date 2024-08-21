"""Support for media browsing."""

import contextlib
from urllib.parse import unquote

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.helpers.network import is_internal_request

LIBRARY = ["Favorites", "Artists", "Albums", "Tracks", "Playlists", "Genres"]

MEDIA_TYPE_TO_SQUEEZEBOX = {
    "Favorites": "favorites",
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
    "favorite": "item_id",
}

CONTENT_TYPE_MEDIA_CLASS = {
    "Favorites": {"item": MediaClass.DIRECTORY, "children": MediaClass.TRACK},
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

FAVORITE_CONTENT_TYPES = {
    "favorite": {
        "media_content_class": "favorite",
        "can_play": True,
        "can_expand": False,
    },
    "folder": {
        "media_content_class": "Favorites",
        "can_play": False,
        "can_expand": True,
    },
    "album": {
        "media_content_class": MediaType.ALBUM,
        "can_play": True,
        "can_expand": True,
    },
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
    "Favorites": MediaType.TRACK,
}

LIBRARY_ICONS = {
    "Artists": "html/images/artists.png",
    "Albums": "html/images/albums.png",
    "Tracks": "html/images/musicfolder.png",
    "Playlists": "html/images/playlists.png",
    "Genres": "html/images/genres.png",
    "Favorites": "html/images/favorites.png",
}

BROWSE_LIMIT = 1000


def _lms_prefix(player):
    return (player.generate_image_url_from_track_id("")).split("music/")[0]

async def _get_album_id(player, url):

    _album_seach_string = unquote(url)[15:].split(
                        "&contributor.name="
                    )
    _album_title = _album_seach_string[0]
    _album_contributor = (
        _album_seach_string[1] if len(_album_seach_string) > 1 else None
    )

    _command = ["albums"]
    _command.extend(
        ["0", str(BROWSE_LIMIT), f"search:{_album_title}", "tags:a"]
    )

    _album_result = await player.async_query(*_command)

    if _album_contributor is None or _album_result["count"] == 1:
        _album_id = _album_result["albums_loop"][0]["id"]
    else:
        for _album in _album_result["albums_loop"]:
            if _album["artist"] == _album_contributor:
                _album_id = _album["id"]
                break
    return str(_album_id)

async def build_item_response(entity, player, payload):
    """Create response payload for search described by payload."""

    internal_request = is_internal_request(entity.hass)

    search_id = payload["search_id"]
    search_type = payload["search_type"]

    media_class = CONTENT_TYPE_MEDIA_CLASS[search_type]

    children = None

    if search_type == "Favorites":
        _command = ["favorites"]
        _command.extend(
            [
                "items",
                "0",
                str(BROWSE_LIMIT),
                f"item_id:{search_id if search_id != "Favorites" else ""}",
                "want_url:1",
            ]
        )

        result = await player.async_query(*_command)

        if result is not None and result.get("loop_loop"):
            children = []
            item_type = CONTENT_TYPE_TO_CHILD_TYPE[search_type]
            child_media_class = CONTENT_TYPE_MEDIA_CLASS[item_type]

            for item in result["loop_loop"]:
                if item.get("type") != "audio" and item.get("hasitems") != 1:
                    continue

                if item["image"].startswith("/imageproxy/"):
                    _icon = unquote(
                        item["image"].split("/imageproxy/")[1].split("/image.png")[0]
                    )
                elif item.get("hasitems") == 1:
                    _icon = _lms_prefix(player) + "html/images/musicfolder.png"
                else:
                    _start = 1 if item["image"].startswith("/") else 0
                    _icon = _lms_prefix(player) + item["image"][_start:]

                if item.get("url", "").startswith("db:album.title"):
                    _type = "album"
                    _album_id = await _get_album_id(player, item.get("url"))
 
                elif item.get("hasitems") == 1:
                    _type = "folder"
                else:
                    _type = "favorite"

                children.append(
                    BrowseMedia(
                        title=item["name"],
                        media_class=child_media_class["item"],
                        media_content_id=item["id"]
                        if _type != "album"
                        else str(_album_id),
                        media_content_type=FAVORITE_CONTENT_TYPES[_type][
                            "media_content_class"
                        ],
                        can_play=FAVORITE_CONTENT_TYPES[_type]["can_play"],
                        can_expand=FAVORITE_CONTENT_TYPES[_type]["can_expand"],
                        thumbnail=_icon,
                    )
                )

    else:
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
        can_play=search_type != "Favorites",
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
        _library_contents_exist = False

        if item == "Favorites":
            _command = ["favorites"]
            _command.extend(["items"])
            result = await player.async_query(*_command)
            if result is not None and result.get("count", 0) > 0:
                _library_contents_exist = True
        else:
            result = await player.async_browse(
                MEDIA_TYPE_TO_SQUEEZEBOX[item],
                limit=1,
            )
            if result is not None and result.get("items") is not None:
                _library_contents_exist = True

        if _library_contents_exist:
            library_info["children"].append(
                BrowseMedia(
                    title=item,
                    media_class=media_class["children"],
                    media_content_id=item,
                    media_content_type=item,
                    can_play=item != "Favorites",
                    can_expand=True,
                    thumbnail=_lms_prefix(player) + LIBRARY_ICONS[item],
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

    return BrowseMedia(**library_info)


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
