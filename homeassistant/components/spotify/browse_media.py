"""Support for Spotify media browsing."""

from __future__ import annotations

from enum import StrEnum
from functools import partial
import logging
from typing import Any

from spotipy import Spotify
import yarl

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import DOMAIN, MEDIA_PLAYER_PREFIX, MEDIA_TYPE_SHOW, PLAYABLE_MEDIA_TYPES
from .util import fetch_image_url

BROWSE_LIMIT = 48


_LOGGER = logging.getLogger(__name__)


class BrowsableMedia(StrEnum):
    """Enum of browsable media."""

    CURRENT_USER_PLAYLISTS = "current_user_playlists"
    CURRENT_USER_FOLLOWED_ARTISTS = "current_user_followed_artists"
    CURRENT_USER_SAVED_ALBUMS = "current_user_saved_albums"
    CURRENT_USER_SAVED_TRACKS = "current_user_saved_tracks"
    CURRENT_USER_SAVED_SHOWS = "current_user_saved_shows"
    CURRENT_USER_RECENTLY_PLAYED = "current_user_recently_played"
    CURRENT_USER_TOP_ARTISTS = "current_user_top_artists"
    CURRENT_USER_TOP_TRACKS = "current_user_top_tracks"
    CATEGORIES = "categories"
    FEATURED_PLAYLISTS = "featured_playlists"
    NEW_RELEASES = "new_releases"


LIBRARY_MAP = {
    BrowsableMedia.CURRENT_USER_PLAYLISTS.value: "Playlists",
    BrowsableMedia.CURRENT_USER_FOLLOWED_ARTISTS.value: "Artists",
    BrowsableMedia.CURRENT_USER_SAVED_ALBUMS.value: "Albums",
    BrowsableMedia.CURRENT_USER_SAVED_TRACKS.value: "Tracks",
    BrowsableMedia.CURRENT_USER_SAVED_SHOWS.value: "Podcasts",
    BrowsableMedia.CURRENT_USER_RECENTLY_PLAYED.value: "Recently played",
    BrowsableMedia.CURRENT_USER_TOP_ARTISTS.value: "Top Artists",
    BrowsableMedia.CURRENT_USER_TOP_TRACKS.value: "Top Tracks",
    BrowsableMedia.CATEGORIES.value: "Categories",
    BrowsableMedia.FEATURED_PLAYLISTS.value: "Featured Playlists",
    BrowsableMedia.NEW_RELEASES.value: "New Releases",
}

CONTENT_TYPE_MEDIA_CLASS: dict[str, Any] = {
    BrowsableMedia.CURRENT_USER_PLAYLISTS.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PLAYLIST,
    },
    BrowsableMedia.CURRENT_USER_FOLLOWED_ARTISTS.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ARTIST,
    },
    BrowsableMedia.CURRENT_USER_SAVED_ALBUMS.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ALBUM,
    },
    BrowsableMedia.CURRENT_USER_SAVED_TRACKS.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.CURRENT_USER_SAVED_SHOWS.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PODCAST,
    },
    BrowsableMedia.CURRENT_USER_RECENTLY_PLAYED.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.CURRENT_USER_TOP_ARTISTS.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ARTIST,
    },
    BrowsableMedia.CURRENT_USER_TOP_TRACKS.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.FEATURED_PLAYLISTS.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PLAYLIST,
    },
    BrowsableMedia.CATEGORIES.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.GENRE,
    },
    "category_playlists": {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PLAYLIST,
    },
    BrowsableMedia.NEW_RELEASES.value: {
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ALBUM,
    },
    MediaType.PLAYLIST: {
        "parent": MediaClass.PLAYLIST,
        "children": MediaClass.TRACK,
    },
    MediaType.ALBUM: {"parent": MediaClass.ALBUM, "children": MediaClass.TRACK},
    MediaType.ARTIST: {"parent": MediaClass.ARTIST, "children": MediaClass.ALBUM},
    MediaType.EPISODE: {"parent": MediaClass.EPISODE, "children": None},
    MEDIA_TYPE_SHOW: {"parent": MediaClass.PODCAST, "children": MediaClass.EPISODE},
    MediaType.TRACK: {"parent": MediaClass.TRACK, "children": None},
}


class MissingMediaInformation(BrowseError):
    """Missing media required information."""


class UnknownMediaType(BrowseError):
    """Unknown media type."""


async def async_browse_media(
    hass: HomeAssistant,
    media_content_type: str | None,
    media_content_id: str | None,
    *,
    can_play_artist: bool = True,
) -> BrowseMedia:
    """Browse Spotify media."""
    parsed_url = None
    info = None

    # Check if caller is requesting the root nodes
    if media_content_type is None and media_content_id is None:
        config_entries = hass.config_entries.async_entries(
            DOMAIN, include_disabled=False, include_ignore=False
        )
        children = [
            BrowseMedia(
                title=config_entry.title,
                media_class=MediaClass.APP,
                media_content_id=f"{MEDIA_PLAYER_PREFIX}{config_entry.entry_id}",
                media_content_type=f"{MEDIA_PLAYER_PREFIX}library",
                thumbnail="https://brands.home-assistant.io/_/spotify/logo.png",
                can_play=False,
                can_expand=True,
            )
            for config_entry in config_entries
        ]
        return BrowseMedia(
            title="Spotify",
            media_class=MediaClass.APP,
            media_content_id=MEDIA_PLAYER_PREFIX,
            media_content_type="spotify",
            thumbnail="https://brands.home-assistant.io/_/spotify/logo.png",
            can_play=False,
            can_expand=True,
            children=children,
        )

    if media_content_id is None or not media_content_id.startswith(MEDIA_PLAYER_PREFIX):
        raise BrowseError("Invalid Spotify URL specified")

    # Check for config entry specifier, and extract Spotify URI
    parsed_url = yarl.URL(media_content_id)
    host = parsed_url.host

    if (
        host is None
        # config entry ids can be upper or lower case. Yarl always returns host
        # names in lower case, so we need to look for the config entry in both
        or (
            entry := hass.config_entries.async_get_entry(host)
            or hass.config_entries.async_get_entry(host.upper())
        )
        is None
        or entry.state is not ConfigEntryState.LOADED
    ):
        raise BrowseError("Invalid Spotify account specified")
    media_content_id = parsed_url.name
    info = entry.runtime_data

    result = await async_browse_media_internal(
        hass,
        info.coordinator.client,
        info.session,
        info.coordinator.current_user,
        media_content_type,
        media_content_id,
        can_play_artist=can_play_artist,
    )

    # Build new URLs with config entry specifyers
    result.media_content_id = str(parsed_url.with_name(result.media_content_id))
    if result.children:
        for child in result.children:
            child.media_content_id = str(parsed_url.with_name(child.media_content_id))
    return result


async def async_browse_media_internal(
    hass: HomeAssistant,
    spotify: Spotify,
    session: OAuth2Session,
    current_user: dict[str, Any],
    media_content_type: str | None,
    media_content_id: str | None,
    *,
    can_play_artist: bool = True,
) -> BrowseMedia:
    """Browse spotify media."""
    if media_content_type in (None, f"{MEDIA_PLAYER_PREFIX}library"):
        return await hass.async_add_executor_job(
            partial(library_payload, can_play_artist=can_play_artist)
        )

    if not session.valid_token:
        await session.async_ensure_token_valid()
        await hass.async_add_executor_job(
            spotify.set_auth, session.token["access_token"]
        )

    # Strip prefix
    if media_content_type:
        media_content_type = media_content_type.removeprefix(MEDIA_PLAYER_PREFIX)

    payload = {
        "media_content_type": media_content_type,
        "media_content_id": media_content_id,
    }
    response = await hass.async_add_executor_job(
        partial(
            build_item_response,
            spotify,
            current_user,
            payload,
            can_play_artist=can_play_artist,
        )
    )
    if response is None:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")
    return response


def build_item_response(  # noqa: C901
    spotify: Spotify,
    user: dict[str, Any],
    payload: dict[str, str | None],
    *,
    can_play_artist: bool,
) -> BrowseMedia | None:
    """Create response payload for the provided media query."""
    media_content_type = payload["media_content_type"]
    media_content_id = payload["media_content_id"]

    if media_content_type is None or media_content_id is None:
        return None

    title = None
    image = None
    media: dict[str, Any] | None = None
    items = []

    if media_content_type == BrowsableMedia.CURRENT_USER_PLAYLISTS:
        if media := spotify.current_user_playlists(limit=BROWSE_LIMIT):
            items = media.get("items", [])
    elif media_content_type == BrowsableMedia.CURRENT_USER_FOLLOWED_ARTISTS:
        if media := spotify.current_user_followed_artists(limit=BROWSE_LIMIT):
            items = media.get("artists", {}).get("items", [])
    elif media_content_type == BrowsableMedia.CURRENT_USER_SAVED_ALBUMS:
        if media := spotify.current_user_saved_albums(limit=BROWSE_LIMIT):
            items = [item["album"] for item in media.get("items", [])]
    elif media_content_type == BrowsableMedia.CURRENT_USER_SAVED_TRACKS:
        if media := spotify.current_user_saved_tracks(limit=BROWSE_LIMIT):
            items = [item["track"] for item in media.get("items", [])]
    elif media_content_type == BrowsableMedia.CURRENT_USER_SAVED_SHOWS:
        if media := spotify.current_user_saved_shows(limit=BROWSE_LIMIT):
            items = [item["show"] for item in media.get("items", [])]
    elif media_content_type == BrowsableMedia.CURRENT_USER_RECENTLY_PLAYED:
        if media := spotify.current_user_recently_played(limit=BROWSE_LIMIT):
            items = [item["track"] for item in media.get("items", [])]
    elif media_content_type == BrowsableMedia.CURRENT_USER_TOP_ARTISTS:
        if media := spotify.current_user_top_artists(limit=BROWSE_LIMIT):
            items = media.get("items", [])
    elif media_content_type == BrowsableMedia.CURRENT_USER_TOP_TRACKS:
        if media := spotify.current_user_top_tracks(limit=BROWSE_LIMIT):
            items = media.get("items", [])
    elif media_content_type == BrowsableMedia.FEATURED_PLAYLISTS:
        if media := spotify.featured_playlists(
            country=user["country"], limit=BROWSE_LIMIT
        ):
            items = media.get("playlists", {}).get("items", [])
    elif media_content_type == BrowsableMedia.CATEGORIES:
        if media := spotify.categories(country=user["country"], limit=BROWSE_LIMIT):
            items = media.get("categories", {}).get("items", [])
    elif media_content_type == "category_playlists":
        if (
            media := spotify.category_playlists(
                category_id=media_content_id,
                country=user["country"],
                limit=BROWSE_LIMIT,
            )
        ) and (category := spotify.category(media_content_id, country=user["country"])):
            title = category.get("name")
            image = fetch_image_url(category, key="icons")
            items = media.get("playlists", {}).get("items", [])
    elif media_content_type == BrowsableMedia.NEW_RELEASES:
        if media := spotify.new_releases(country=user["country"], limit=BROWSE_LIMIT):
            items = media.get("albums", {}).get("items", [])
    elif media_content_type == MediaType.PLAYLIST:
        if media := spotify.playlist(media_content_id):
            items = [item["track"] for item in media.get("tracks", {}).get("items", [])]
    elif media_content_type == MediaType.ALBUM:
        if media := spotify.album(media_content_id):
            items = media.get("tracks", {}).get("items", [])
    elif media_content_type == MediaType.ARTIST:
        if (media := spotify.artist_albums(media_content_id, limit=BROWSE_LIMIT)) and (
            artist := spotify.artist(media_content_id)
        ):
            title = artist.get("name")
            image = fetch_image_url(artist)
            items = media.get("items", [])
    elif media_content_type == MEDIA_TYPE_SHOW:
        if (media := spotify.show_episodes(media_content_id, limit=BROWSE_LIMIT)) and (
            show := spotify.show(media_content_id)
        ):
            title = show.get("name")
            image = fetch_image_url(show)
            items = media.get("items", [])

    if media is None:
        return None

    try:
        media_class = CONTENT_TYPE_MEDIA_CLASS[media_content_type]
    except KeyError:
        _LOGGER.debug("Unknown media type received: %s", media_content_type)
        return None

    if media_content_type == BrowsableMedia.CATEGORIES:
        media_item = BrowseMedia(
            can_expand=True,
            can_play=False,
            children_media_class=media_class["children"],
            media_class=media_class["parent"],
            media_content_id=media_content_id,
            media_content_type=f"{MEDIA_PLAYER_PREFIX}{media_content_type}",
            title=LIBRARY_MAP.get(media_content_id, "Unknown"),
        )

        media_item.children = []
        for item in items:
            try:
                item_id = item["id"]
            except KeyError:
                _LOGGER.debug("Missing ID for media item: %s", item)
                continue
            media_item.children.append(
                BrowseMedia(
                    can_expand=True,
                    can_play=False,
                    children_media_class=MediaClass.TRACK,
                    media_class=MediaClass.PLAYLIST,
                    media_content_id=item_id,
                    media_content_type=f"{MEDIA_PLAYER_PREFIX}category_playlists",
                    thumbnail=fetch_image_url(item, key="icons"),
                    title=item.get("name"),
                )
            )
        return media_item

    if title is None:
        title = LIBRARY_MAP.get(media_content_id, "Unknown")
        if "name" in media:
            title = media["name"]

    can_play = media_content_type in PLAYABLE_MEDIA_TYPES and (
        media_content_type != MediaType.ARTIST or can_play_artist
    )

    browse_media = BrowseMedia(
        can_expand=True,
        can_play=can_play,
        children_media_class=media_class["children"],
        media_class=media_class["parent"],
        media_content_id=media_content_id,
        media_content_type=f"{MEDIA_PLAYER_PREFIX}{media_content_type}",
        thumbnail=image,
        title=title,
    )

    browse_media.children = []
    for item in items:
        try:
            browse_media.children.append(
                item_payload(item, can_play_artist=can_play_artist)
            )
        except (MissingMediaInformation, UnknownMediaType):
            continue

    if "images" in media:
        browse_media.thumbnail = fetch_image_url(media)

    return browse_media


def item_payload(item: dict[str, Any], *, can_play_artist: bool) -> BrowseMedia:
    """Create response payload for a single media item.

    Used by async_browse_media.
    """
    try:
        media_type = item["type"]
        media_id = item["uri"]
    except KeyError as err:
        _LOGGER.debug("Missing type or URI for media item: %s", item)
        raise MissingMediaInformation from err

    try:
        media_class = CONTENT_TYPE_MEDIA_CLASS[media_type]
    except KeyError as err:
        _LOGGER.debug("Unknown media type received: %s", media_type)
        raise UnknownMediaType from err

    can_expand = media_type not in [
        MediaType.TRACK,
        MediaType.EPISODE,
    ]

    can_play = media_type in PLAYABLE_MEDIA_TYPES and (
        media_type != MediaType.ARTIST or can_play_artist
    )

    browse_media = BrowseMedia(
        can_expand=can_expand,
        can_play=can_play,
        children_media_class=media_class["children"],
        media_class=media_class["parent"],
        media_content_id=media_id,
        media_content_type=f"{MEDIA_PLAYER_PREFIX}{media_type}",
        title=item.get("name", "Unknown"),
    )

    if "images" in item:
        browse_media.thumbnail = fetch_image_url(item)
    elif MediaType.ALBUM in item:
        browse_media.thumbnail = fetch_image_url(item[MediaType.ALBUM])

    return browse_media


def library_payload(*, can_play_artist: bool) -> BrowseMedia:
    """Create response payload to describe contents of a specific library.

    Used by async_browse_media.
    """
    browse_media = BrowseMedia(
        can_expand=True,
        can_play=False,
        children_media_class=MediaClass.DIRECTORY,
        media_class=MediaClass.DIRECTORY,
        media_content_id="library",
        media_content_type=f"{MEDIA_PLAYER_PREFIX}library",
        title="Media Library",
    )

    browse_media.children = []
    for item in [{"name": n, "type": t} for t, n in LIBRARY_MAP.items()]:
        browse_media.children.append(
            item_payload(
                {"name": item["name"], "type": item["type"], "uri": item["type"]},
                can_play_artist=can_play_artist,
            )
        )
    return browse_media
