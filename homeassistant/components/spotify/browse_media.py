"""Support for Spotify media browsing."""

from __future__ import annotations

from enum import StrEnum
import logging
from typing import Any, TypedDict

from spotifyaio import SpotifyClient
import yarl

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import DOMAIN, MEDIA_PLAYER_PREFIX, MEDIA_TYPE_SHOW, PLAYABLE_MEDIA_TYPES

BROWSE_LIMIT = 48


_LOGGER = logging.getLogger(__name__)


class ItemPayload(TypedDict):
    """TypedDict for item payload."""

    name: str
    type: str
    uri: str
    id: str | None
    thumbnail: str | None


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
        info.coordinator.current_user,
        media_content_type,
        media_content_id,
        can_play_artist=can_play_artist,
    )

    # Build new URLs with config entry specifiers
    result.media_content_id = str(parsed_url.with_name(result.media_content_id))
    if result.children:
        for child in result.children:
            child.media_content_id = str(parsed_url.with_name(child.media_content_id))
    return result


async def async_browse_media_internal(
    hass: HomeAssistant,
    spotify: SpotifyClient,
    current_user: dict[str, Any],
    media_content_type: str | None,
    media_content_id: str | None,
    *,
    can_play_artist: bool = True,
) -> BrowseMedia:
    """Browse spotify media."""
    if media_content_type in (None, f"{MEDIA_PLAYER_PREFIX}library"):
        return await library_payload(can_play_artist=can_play_artist)

    # Strip prefix
    if media_content_type:
        media_content_type = media_content_type.removeprefix(MEDIA_PLAYER_PREFIX)

    payload = {
        "media_content_type": media_content_type,
        "media_content_id": media_content_id,
    }
    response = await build_item_response(
        spotify,
        current_user,
        payload,
        can_play_artist=can_play_artist,
    )
    if response is None:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")
    return response


async def build_item_response(  # noqa: C901
    spotify: SpotifyClient,
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

    title: str | None = None
    image: str | None = None
    items: list[ItemPayload] = []

    if media_content_type == BrowsableMedia.CURRENT_USER_PLAYLISTS:
        if playlists := await spotify.get_playlists_for_current_user():
            items = [
                {
                    "id": playlist.playlist_id,
                    "name": playlist.name,
                    "type": MediaType.PLAYLIST,
                    "uri": playlist.uri,
                    "thumbnail": playlist.images[0].url if playlist.images else None,
                }
                for playlist in playlists
            ]
    elif media_content_type == BrowsableMedia.CURRENT_USER_FOLLOWED_ARTISTS:
        if artists := await spotify.get_followed_artists():
            items = [
                {
                    "id": artist.artist_id,
                    "name": artist.name,
                    "type": MediaType.ARTIST,
                    "uri": artist.uri,
                    "thumbnail": artist.images[0].url if artist.images else None,
                }
                for artist in artists
            ]
    elif media_content_type == BrowsableMedia.CURRENT_USER_SAVED_ALBUMS:
        if saved_albums := await spotify.get_saved_albums():
            items = [
                {
                    "id": saved_album.album.album_id,
                    "name": saved_album.album.name,
                    "type": MediaType.ALBUM,
                    "uri": saved_album.album.uri,
                    "thumbnail": saved_album.album.images[0].url
                    if saved_album.album.images
                    else None,
                }
                for saved_album in saved_albums
            ]
    elif media_content_type == BrowsableMedia.CURRENT_USER_SAVED_TRACKS:
        if media := await spotify.get_saved_tracks():
            items = [
                {
                    "id": saved_track.track.track_id,
                    "name": saved_track.track.name,
                    "type": MediaType.TRACK,
                    "uri": saved_track.track.uri,
                    "thumbnail": saved_track.track.album.images[0].url
                    if saved_track.track.album.images
                    else None,
                }
                for saved_track in media
            ]
    elif media_content_type == BrowsableMedia.CURRENT_USER_SAVED_SHOWS:
        if media := await spotify.get_saved_shows():
            items = [
                {
                    "id": saved_show.show.show_id,
                    "name": saved_show.show.name,
                    "type": MEDIA_TYPE_SHOW,
                    "uri": saved_show.show.uri,
                    "thumbnail": saved_show.show.images[0].url
                    if saved_show.show.images
                    else None,
                }
                for saved_show in media
            ]
    elif media_content_type == BrowsableMedia.CURRENT_USER_RECENTLY_PLAYED:
        if media := await spotify.get_recently_played_tracks():
            items = [
                {
                    "id": item.track.track_id,
                    "name": item.track.name,
                    "type": MediaType.TRACK,
                    "uri": item.track.uri,
                    "thumbnail": item.track.album.images[0].url
                    if item.track.album.images
                    else None,
                }
                for item in media
            ]
    elif media_content_type == BrowsableMedia.CURRENT_USER_TOP_ARTISTS:
        if media := await spotify.get_top_artists():
            items = [
                {
                    "id": artist.artist_id,
                    "name": artist.name,
                    "type": MediaType.ARTIST,
                    "uri": artist.uri,
                    "thumbnail": artist.images[0].url if artist.images else None,
                }
                for artist in media
            ]
    elif media_content_type == BrowsableMedia.CURRENT_USER_TOP_TRACKS:
        if media := await spotify.get_top_tracks():
            items = [
                {
                    "id": track.track_id,
                    "name": track.name,
                    "type": MediaType.TRACK,
                    "uri": track.uri,
                    "thumbnail": track.album.images[0].url
                    if track.album.images
                    else None,
                }
                for track in media
            ]
    elif media_content_type == BrowsableMedia.FEATURED_PLAYLISTS:
        if media := await spotify.get_featured_playlists():
            items = [
                {
                    "id": playlist.playlist_id,
                    "name": playlist.name,
                    "type": MediaType.PLAYLIST,
                    "uri": playlist.uri,
                    "thumbnail": playlist.images[0].url if playlist.images else None,
                }
                for playlist in media
            ]
    elif media_content_type == BrowsableMedia.CATEGORIES:
        if media := await spotify.get_category(user["country"]):
            items = [
                {
                    "id": category.id,
                    "name": category.name,
                    "type": "category_playlists",
                    "uri": category.id,
                    "thumbnail": category.icons[0].url if category.icons else None,
                }
                for category in media
            ]
    elif media_content_type == "category_playlists":
        if (
            media := await spotify.get_category_playlists(category_id=media_content_id)
        ) and (category := await spotify.get_category(media_content_id)):
            title = category.name
            image = category.icons[0].url if category.icons else None
            items = [
                {
                    "id": playlist.playlist_id,
                    "name": playlist.name,
                    "type": MediaType.PLAYLIST,
                    "uri": playlist.uri,
                    "thumbnail": playlist.images[0].url if playlist.images else None,
                }
                for playlist in media
            ]
    elif media_content_type == BrowsableMedia.NEW_RELEASES:
        if media := await spotify.get_new_releases():
            items = [
                {
                    "id": album.album_id,
                    "name": album.name,
                    "type": MediaType.ALBUM,
                    "uri": album.uri,
                    "thumbnail": album.images[0].url if album.images else None,
                }
                for album in media
            ]
    elif media_content_type == MediaType.PLAYLIST:
        if media := await spotify.get_playlist(media_content_id):
            items = [
                {
                    "id": track.track_id,
                    "name": track.name,
                    "type": MediaType.TRACK,
                    "uri": track.uri,
                    "thumbnail": track.album.images[0].url
                    if track.album.images
                    else None,
                }
                for track in media.tracks
            ]
    elif media_content_type == MediaType.ALBUM:
        if media := await spotify.get_album(media_content_id):
            items = [
                {
                    "id": track.track_id,
                    "name": track.name,
                    "type": MediaType.TRACK,
                    "uri": track.uri,
                    "thumbnail": track.album.images[0].url
                    if track.album.images
                    else None,
                }
                for track in media.tracks
            ]
    elif media_content_type == MediaType.ARTIST:
        if (media := await spotify.get_artist_albums(media_content_id)) and (
            artist := await spotify.get_artist(media_content_id)
        ):
            title = artist.name
            image = artist.images[0].url if artist.images else None
            items = [
                {
                    "id": album.album_id,
                    "name": album.name,
                    "type": MediaType.ALBUM,
                    "uri": album.uri,
                    "thumbnail": album.images[0].url if album.images else None,
                }
                for album in media
            ]
    elif media_content_type == MEDIA_TYPE_SHOW:
        if (media := await spotify.get_show_episodes(media_content_id)) and (
            show := await spotify.get_show(media_content_id)
        ):
            title = show.name
            image = show.images[0].url if show.images else None
            items = [
                {
                    "id": episode.episode_id,
                    "name": episode.name,
                    "type": MediaType.EPISODE,
                    "uri": episode.uri,
                    "thumbnail": episode.images[0].url if episode.images else None,
                }
                for episode in media
            ]

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
            if (item_id := item["id"]) is None:
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
                    thumbnail=item["thumbnail"],
                    title=item["name"],
                )
            )
        return media_item

    if title is None:
        title = LIBRARY_MAP.get(media_content_id, "Unknown")

    can_play = media_content_type in PLAYABLE_MEDIA_TYPES and (
        media_content_type != MediaType.ARTIST or can_play_artist
    )

    assert title
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

    return browse_media


def item_payload(item: ItemPayload, *, can_play_artist: bool) -> BrowseMedia:
    """Create response payload for a single media item.

    Used by async_browse_media.
    """
    media_type = item["type"]
    media_id = item["uri"]

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

    return BrowseMedia(
        can_expand=can_expand,
        can_play=can_play,
        children_media_class=media_class["children"],
        media_class=media_class["parent"],
        media_content_id=media_id,
        media_content_type=f"{MEDIA_PLAYER_PREFIX}{media_type}",
        title=item["name"],
        thumbnail=item["thumbnail"],
    )


async def library_payload(*, can_play_artist: bool) -> BrowseMedia:
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
    for item_type, item_name in LIBRARY_MAP.items():
        browse_media.children.append(
            item_payload(
                {
                    "name": item_name,
                    "type": item_type,
                    "uri": item_type,
                    "id": None,
                    "thumbnail": None,
                },
                can_play_artist=can_play_artist,
            )
        )
    return browse_media
