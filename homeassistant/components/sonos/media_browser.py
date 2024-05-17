"""Support for media browsing."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from functools import partial
import logging
from typing import cast
import urllib.parse

from soco.data_structures import DidlObject
from soco.ms_data_structures import MusicServiceItem
from soco.music_library import MusicLibrary

from homeassistant.components import media_source, plex, spotify
from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import is_internal_request

from .const import (
    DOMAIN,
    EXPANDABLE_MEDIA_TYPES,
    LIBRARY_TITLES_MAPPING,
    MEDIA_TYPES_TO_SONOS,
    PLAYABLE_MEDIA_TYPES,
    SONOS_ALBUM,
    SONOS_ALBUM_ARTIST,
    SONOS_GENRE,
    SONOS_TO_MEDIA_CLASSES,
    SONOS_TO_MEDIA_TYPES,
    SONOS_TRACKS,
    SONOS_TYPES_MAPPING,
)
from .exception import UnknownMediaType
from .favorites import SonosFavorites
from .speaker import SonosMedia, SonosSpeaker

_LOGGER = logging.getLogger(__name__)

type GetBrowseImageUrlType = Callable[[str, str, str | None], str]


def get_thumbnail_url_full(
    media: SonosMedia,
    is_internal: bool,
    get_browse_image_url: GetBrowseImageUrlType,
    media_content_type: str,
    media_content_id: str,
    media_image_id: str | None = None,
) -> str | None:
    """Get thumbnail URL."""
    if is_internal:
        item = get_media(
            media.library,
            media_content_id,
            media_content_type,
        )
        return urllib.parse.unquote(getattr(item, "album_art_uri", ""))

    return urllib.parse.unquote(
        get_browse_image_url(
            media_content_type,
            media_content_id,
            media_image_id,
        )
    )


def media_source_filter(item: BrowseMedia) -> bool:
    """Filter media sources."""
    return item.media_content_type.startswith("audio/")


async def async_browse_media(
    hass: HomeAssistant,
    speaker: SonosSpeaker,
    media: SonosMedia,
    get_browse_image_url: GetBrowseImageUrlType,
    media_content_id: str | None,
    media_content_type: str | None,
) -> BrowseMedia:
    """Browse media."""

    if media_content_id is None:
        return await root_payload(
            hass,
            speaker,
            media,
            get_browse_image_url,
        )
    assert media_content_type is not None

    if media_source.is_media_source_id(media_content_id):
        return await media_source.async_browse_media(
            hass, media_content_id, content_filter=media_source_filter
        )

    if plex.is_plex_media_id(media_content_id):
        return await plex.async_browse_media(
            hass, media_content_type, media_content_id, platform=DOMAIN
        )

    if media_content_type == "plex":
        return await plex.async_browse_media(hass, None, None, platform=DOMAIN)

    if spotify.is_spotify_media_type(media_content_type):
        return await spotify.async_browse_media(
            hass, media_content_type, media_content_id, can_play_artist=False
        )

    if media_content_type == "library":
        return await hass.async_add_executor_job(
            library_payload,
            media.library,
            partial(
                get_thumbnail_url_full,
                media,
                is_internal_request(hass),
                get_browse_image_url,
            ),
        )

    if media_content_type == "favorites":
        return await hass.async_add_executor_job(
            favorites_payload,
            speaker.favorites,
        )

    if media_content_type == "favorites_folder":
        return await hass.async_add_executor_job(
            favorites_folder_payload,
            speaker.favorites,
            media_content_id,
        )

    payload = {
        "search_type": media_content_type,
        "idstring": media_content_id,
    }
    response = await hass.async_add_executor_job(
        build_item_response,
        media.library,
        payload,
        partial(
            get_thumbnail_url_full,
            media,
            is_internal_request(hass),
            get_browse_image_url,
        ),
    )
    if response is None:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")
    return response


def build_item_response(
    media_library: MusicLibrary, payload: dict[str, str], get_thumbnail_url=None
) -> BrowseMedia | None:
    """Create response payload for the provided media query."""
    if payload["search_type"] == MediaType.ALBUM and payload["idstring"].startswith(
        ("A:GENRE", "A:COMPOSER")
    ):
        payload["idstring"] = "A:ALBUMARTIST/" + "/".join(
            payload["idstring"].split("/")[2:]
        )
        payload["idstring"] = urllib.parse.unquote(payload["idstring"])

    try:
        search_type = MEDIA_TYPES_TO_SONOS[payload["search_type"]]
    except KeyError:
        _LOGGER.debug(
            "Unknown media type received when building item response: %s",
            payload["search_type"],
        )
        return None

    media = media_library.browse_by_idstring(
        search_type,
        payload["idstring"],
        full_album_art_uri=True,
        max_items=0,
    )

    if media is None:
        return None

    thumbnail = None
    title = None

    # Fetch album info for titles and thumbnails
    # Can't be extracted from track info
    if (
        payload["search_type"] == MediaType.ALBUM
        and media[0].item_class == "object.item.audioItem.musicTrack"
    ):
        idstring = payload["idstring"]
        if idstring.startswith("A:ALBUMARTIST/"):
            search_type = SONOS_ALBUM_ARTIST
        elif idstring.startswith("A:ALBUM/"):
            search_type = SONOS_ALBUM
        item = get_media(media_library, idstring, search_type)

        title = getattr(item, "title", None)
        thumbnail = get_thumbnail_url(search_type, payload["idstring"])

    if not title:
        try:
            title = urllib.parse.unquote(payload["idstring"].split("/")[1])
        except IndexError:
            title = LIBRARY_TITLES_MAPPING[payload["idstring"]]

    try:
        media_class = SONOS_TO_MEDIA_CLASSES[
            MEDIA_TYPES_TO_SONOS[payload["search_type"]]
        ]
    except KeyError:
        _LOGGER.debug("Unknown media type received %s", payload["search_type"])
        return None

    children = []
    for item in media:
        with suppress(UnknownMediaType):
            children.append(item_payload(item, get_thumbnail_url))

    return BrowseMedia(
        title=title,
        thumbnail=thumbnail,
        media_class=media_class,
        media_content_id=payload["idstring"],
        media_content_type=payload["search_type"],
        children=children,
        can_play=can_play(payload["search_type"]),
        can_expand=can_expand(payload["search_type"]),
    )


def item_payload(item: DidlObject, get_thumbnail_url=None) -> BrowseMedia:
    """Create response payload for a single media item.

    Used by async_browse_media.
    """
    media_type = get_media_type(item)
    try:
        media_class = SONOS_TO_MEDIA_CLASSES[media_type]
    except KeyError as err:
        _LOGGER.debug("Unknown media type received %s", media_type)
        raise UnknownMediaType from err

    content_id = get_content_id(item)
    thumbnail = None
    if getattr(item, "album_art_uri", None):
        thumbnail = get_thumbnail_url(media_class, content_id)

    return BrowseMedia(
        title=item.title,
        thumbnail=thumbnail,
        media_class=media_class,
        media_content_id=content_id,
        media_content_type=SONOS_TO_MEDIA_TYPES[media_type],
        can_play=can_play(item.item_class),
        can_expand=can_expand(item),
    )


async def root_payload(
    hass: HomeAssistant,
    speaker: SonosSpeaker,
    media: SonosMedia,
    get_browse_image_url: GetBrowseImageUrlType,
) -> BrowseMedia:
    """Return root payload for Sonos."""
    children: list[BrowseMedia] = []

    if speaker.favorites:
        children.append(
            BrowseMedia(
                title="Favorites",
                media_class=MediaClass.DIRECTORY,
                media_content_id="",
                media_content_type="favorites",
                thumbnail="https://brands.home-assistant.io/_/sonos/logo.png",
                can_play=False,
                can_expand=True,
            )
        )

    if await hass.async_add_executor_job(
        partial(media.library.browse_by_idstring, "tracks", "", max_items=1)
    ):
        children.append(
            BrowseMedia(
                title="Music Library",
                media_class=MediaClass.DIRECTORY,
                media_content_id="",
                media_content_type="library",
                thumbnail="https://brands.home-assistant.io/_/sonos/logo.png",
                can_play=False,
                can_expand=True,
            )
        )

    if "plex" in hass.config.components:
        children.append(
            BrowseMedia(
                title="Plex",
                media_class=MediaClass.APP,
                media_content_id="",
                media_content_type="plex",
                thumbnail="https://brands.home-assistant.io/_/plex/logo.png",
                can_play=False,
                can_expand=True,
            )
        )

    if "spotify" in hass.config.components:
        result = await spotify.async_browse_media(hass, None, None)
        if result.children:
            children.extend(result.children)

    try:
        item = await media_source.async_browse_media(
            hass, None, content_filter=media_source_filter
        )
        # If domain is None, it's overview of available sources
        if item.domain is None and item.children is not None:
            children.extend(item.children)
        else:
            children.append(item)
    except media_source.BrowseError:
        pass

    if len(children) == 1:
        return await async_browse_media(
            hass,
            speaker,
            media,
            get_browse_image_url,
            children[0].media_content_id,
            children[0].media_content_type,
        )

    return BrowseMedia(
        title="Sonos",
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="root",
        can_play=False,
        can_expand=True,
        children=children,
    )


def library_payload(media_library: MusicLibrary, get_thumbnail_url=None) -> BrowseMedia:
    """Create response payload to describe contents of a specific library.

    Used by async_browse_media.
    """
    children = []
    for item in media_library.browse():
        with suppress(UnknownMediaType):
            children.append(item_payload(item, get_thumbnail_url))

    return BrowseMedia(
        title="Music Library",
        media_class=MediaClass.DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        can_play=False,
        can_expand=True,
        children=children,
    )


def favorites_payload(favorites: SonosFavorites) -> BrowseMedia:
    """Create response payload to describe contents of a specific library.

    Used by async_browse_media.
    """
    children: list[BrowseMedia] = []

    group_types: set[str] = {fav.reference.item_class for fav in favorites}
    for group_type in sorted(group_types):
        try:
            media_content_type = SONOS_TYPES_MAPPING[group_type]
            media_class = SONOS_TO_MEDIA_CLASSES[group_type]
        except KeyError:
            _LOGGER.debug("Unknown media type or class received %s", group_type)
            continue
        children.append(
            BrowseMedia(
                title=media_content_type.title(),
                media_class=media_class,
                media_content_id=group_type,
                media_content_type="favorites_folder",
                can_play=False,
                can_expand=True,
            )
        )

    return BrowseMedia(
        title="Favorites",
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="favorites",
        can_play=False,
        can_expand=True,
        children=children,
    )


def favorites_folder_payload(
    favorites: SonosFavorites, media_content_id: str
) -> BrowseMedia:
    """Create response payload to describe all items of a type of favorite.

    Used by async_browse_media.
    """
    children: list[BrowseMedia] = []
    content_type = SONOS_TYPES_MAPPING[media_content_id]

    for favorite in favorites:
        if favorite.reference.item_class != media_content_id:
            continue
        children.append(
            BrowseMedia(
                title=favorite.title,
                media_class=SONOS_TO_MEDIA_CLASSES[favorite.reference.item_class],
                media_content_id=favorite.item_id,
                media_content_type="favorite_item_id",
                can_play=True,
                can_expand=False,
                thumbnail=getattr(favorite, "album_art_uri", None),
            )
        )

    return BrowseMedia(
        title=content_type.title(),
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="favorites",
        can_play=False,
        can_expand=True,
        children=children,
    )


def get_media_type(item: DidlObject) -> str:
    """Extract media type of item."""
    if item.item_class == "object.item.audioItem.musicTrack":
        return SONOS_TRACKS

    if (
        item.item_class == "object.container.album.musicAlbum"
        and SONOS_TYPES_MAPPING.get(item.item_id.split("/")[0])
        in [
            SONOS_ALBUM_ARTIST,
            SONOS_GENRE,
        ]
    ):
        return SONOS_TYPES_MAPPING[item.item_class]

    return SONOS_TYPES_MAPPING.get(item.item_id.split("/")[0], item.item_class)


def can_play(item: DidlObject) -> bool:
    """Test if playable.

    Used by async_browse_media.
    """
    return SONOS_TO_MEDIA_TYPES.get(item) in PLAYABLE_MEDIA_TYPES


def can_expand(item: DidlObject) -> bool:
    """Test if expandable.

    Used by async_browse_media.
    """
    if isinstance(item, str):
        return SONOS_TYPES_MAPPING.get(item) in EXPANDABLE_MEDIA_TYPES

    if SONOS_TO_MEDIA_TYPES.get(item.item_class) in EXPANDABLE_MEDIA_TYPES:
        return True

    return SONOS_TYPES_MAPPING.get(item.item_id) in EXPANDABLE_MEDIA_TYPES


def get_content_id(item: DidlObject) -> str:
    """Extract content id or uri."""
    if item.item_class == "object.item.audioItem.musicTrack":
        return cast(str, item.get_uri())
    return cast(str, item.item_id)


def get_media(
    media_library: MusicLibrary, item_id: str, search_type: str
) -> MusicServiceItem | None:
    """Fetch a single media/album."""
    _LOGGER.debug("get_media item_id [%s], search_type [%s]", item_id, search_type)
    search_type = MEDIA_TYPES_TO_SONOS.get(search_type, search_type)

    if search_type == "playlists":
        # Format is S:TITLE or S:ITEM_ID
        splits = item_id.split(":")
        title = splits[1] if len(splits) > 1 else None
        return next(
            (
                p
                for p in media_library.get_playlists()
                if (item_id == p.item_id or title == p.title)
            ),
            None,
        )

    if not item_id.startswith("A:ALBUM") and search_type == SONOS_ALBUM:
        item_id = "A:ALBUMARTIST/" + "/".join(item_id.split("/")[2:])

    if item_id.startswith("A:ALBUM/") or search_type == "tracks":
        search_term = urllib.parse.unquote(item_id.split("/")[-1])
        matches = media_library.get_music_library_information(
            search_type, search_term=search_term, full_album_art_uri=True
        )
    else:
        # When requesting media by album_artist, composer, genre use the browse interface
        # to navigate the hierarchy. This occurs when invoked from media browser or service
        # calls
        # Example: A:ALBUMARTIST/Neil Young/Greatest Hits - get specific album
        # Example: A:ALBUMARTIST/Neil Young - get all albums
        # Others: composer, genre
        # A:<topic>/<name>/<optional title>
        splits = item_id.split("/")
        title = urllib.parse.unquote(splits[2]) if len(splits) > 2 else None
        browse_id_string = splits[0] + "/" + splits[1]
        matches = media_library.browse_by_idstring(
            search_type, browse_id_string, full_album_art_uri=True
        )
        if title:
            result = next(
                (item for item in matches if (title == item.title)),
                None,
            )
            matches = [result]

    _LOGGER.debug(
        "get_media search_type [%s] item_id [%s] matches [%d]",
        search_type,
        item_id,
        len(matches),
    )
    if len(matches) > 0:
        return matches[0]
    return None
