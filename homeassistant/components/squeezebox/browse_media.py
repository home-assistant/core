"""Support for media browsing."""
import asyncio
import hashlib
import logging
from random import SystemRandom

from aiohttp import web
from aiohttp.hdrs import CACHE_CONTROL, CONTENT_TYPE
import async_timeout

from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
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
from homeassistant.const import HTTP_INTERNAL_SERVER_ERROR, HTTP_OK, HTTP_UNAUTHORIZED

_LOGGER = logging.getLogger(__name__)

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
    MEDIA_TYPE_PLAYLIST: {"item": MEDIA_CLASS_PLAYLIST, "children": MEDIA_CLASS_TRACK},
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


async def build_item_response(player, payload, internal_artwork_url, base_url):
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
        token = SqueezeboxArtworkProxy.access_token

        children = []
        for item in result["items"]:
            thumbnail = item.get("image_url")
            if thumbnail and thumbnail.startswith(internal_artwork_url):
                thumbnail = (
                    f"{base_url}/api/squeezebox_proxy?token={token}&artwork={thumbnail}"
                )

            children.append(
                BrowseMedia(
                    title=item["title"],
                    media_class=child_media_class["item"],
                    media_content_id=str(item["id"]),
                    media_content_type=item_type,
                    can_play=True,
                    can_expand=child_media_class["children"] is not None,
                    thumbnail=thumbnail,
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


class SqueezeboxArtworkProxy(HomeAssistantView):
    """View to proxy album art."""

    requires_auth = False
    url = "/api/squeezebox_proxy"
    name = "api:squeezebox:image"
    access_token = hashlib.sha256(
        SystemRandom().getrandbits(256).to_bytes(32, "little")
    ).hexdigest()
    internal_artwork_urls = []

    def __init__(self, session, artwork_url):
        """Initialize a Squeezebox view."""
        self.session = session
        if artwork_url not in self.internal_artwork_urls:
            self.internal_artwork_urls.append(artwork_url)

    async def get(self, request):
        """Start a get request."""
        authenticated = (
            request[KEY_AUTHENTICATED]
            or request.query.get("token") == self.access_token
        )

        if not authenticated:
            return web.Response(status=HTTP_UNAUTHORIZED)

        data, content_type = await self.async_get_artwork(request.query.get("artwork"))

        if data is None:
            return web.Response(status=HTTP_INTERNAL_SERVER_ERROR)

        headers = {CACHE_CONTROL: "max-age=3600"}
        return web.Response(body=data, content_type=content_type, headers=headers)

    async def async_get_artwork(self, artwork):
        """Get album art from Squeezebox server."""
        is_internal = next(
            (True for url in self.internal_artwork_urls if artwork.startswith(url)),
            False,
        )
        if is_internal:
            try:
                with async_timeout.timeout(5):
                    response = await self.session.get(artwork)

                    if response.status == HTTP_OK:
                        content = await response.read()
                        content_type = response.headers.get(CONTENT_TYPE)
                        if content_type:
                            content_type = content_type.split(";")[0]
                        return (content, content_type)
            except asyncio.TimeoutError:
                pass
        return (None, None)
