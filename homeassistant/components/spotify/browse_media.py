"""Support for Spotify media browsing."""

from __future__ import annotations

from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any, TypedDict

from spotifyaio import (
    Artist,
    BasePlaylist,
    SimplifiedAlbum,
    SimplifiedTrack,
    SpotifyClient,
    Track,
)
from spotifyaio.models import ItemType, SimplifiedEpisode
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
from .util import fetch_image_url

BROWSE_LIMIT = 48


_LOGGER = logging.getLogger(__name__)


class ItemPayload(TypedDict):
    """TypedDict for item payload."""

    name: str
    type: str
    uri: str
    id: str | None
    thumbnail: str | None


def _get_artist_item_payload(artist: Artist) -> ItemPayload:
    return {
        "id": artist.artist_id,
        "name": artist.name,
        "type": MediaType.ARTIST,
        "uri": artist.uri,
        "thumbnail": fetch_image_url(artist.images),
    }


def _get_album_item_payload(album: SimplifiedAlbum) -> ItemPayload:
    return {
        "id": album.album_id,
        "name": album.name,
        "type": MediaType.ALBUM,
        "uri": album.uri,
        "thumbnail": fetch_image_url(album.images),
    }


def _get_playlist_item_payload(playlist: BasePlaylist) -> ItemPayload:
    return {
        "id": playlist.playlist_id,
        "name": playlist.name,
        "type": MediaType.PLAYLIST,
        "uri": playlist.uri,
        "thumbnail": fetch_image_url(playlist.images),
    }


def _get_track_item_payload(
    track: SimplifiedTrack, show_thumbnails: bool = True
) -> ItemPayload:
    return {
        "id": track.track_id,
        "name": track.name,
        "type": MediaType.TRACK,
        "uri": track.uri,
        "thumbnail": (
            fetch_image_url(track.album.images)
            if show_thumbnails and isinstance(track, Track)
            else None
        ),
    }


def _get_episode_item_payload(episode: SimplifiedEpisode) -> ItemPayload:
    return {
        "id": episode.episode_id,
        "name": episode.name,
        "type": MediaType.EPISODE,
        "uri": episode.uri,
        "thumbnail": fetch_image_url(episode.images),
    }


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
        payload,
        can_play_artist=can_play_artist,
    )
    if response is None:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")
    return response


async def build_item_response(  # noqa: C901
    spotify: SpotifyClient,
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
            items = [_get_playlist_item_payload(playlist) for playlist in playlists]
    elif media_content_type == BrowsableMedia.CURRENT_USER_FOLLOWED_ARTISTS:
        if artists := await spotify.get_followed_artists():
            items = [_get_artist_item_payload(artist) for artist in artists]
    elif media_content_type == BrowsableMedia.CURRENT_USER_SAVED_ALBUMS:
        if saved_albums := await spotify.get_saved_albums():
            items = [
                _get_album_item_payload(saved_album.album)
                for saved_album in saved_albums
            ]
    elif media_content_type == BrowsableMedia.CURRENT_USER_SAVED_TRACKS:
        if saved_tracks := await spotify.get_saved_tracks():
            items = [
                _get_track_item_payload(saved_track.track)
                for saved_track in saved_tracks
            ]
    elif media_content_type == BrowsableMedia.CURRENT_USER_SAVED_SHOWS:
        if saved_shows := await spotify.get_saved_shows():
            items = [
                {
                    "id": saved_show.show.show_id,
                    "name": saved_show.show.name,
                    "type": MEDIA_TYPE_SHOW,
                    "uri": saved_show.show.uri,
                    "thumbnail": fetch_image_url(saved_show.show.images),
                }
                for saved_show in saved_shows
            ]
    elif media_content_type == BrowsableMedia.CURRENT_USER_RECENTLY_PLAYED:
        if recently_played_tracks := await spotify.get_recently_played_tracks():
            items = [
                _get_track_item_payload(item.track) for item in recently_played_tracks
            ]
    elif media_content_type == BrowsableMedia.CURRENT_USER_TOP_ARTISTS:
        if top_artists := await spotify.get_top_artists():
            items = [_get_artist_item_payload(artist) for artist in top_artists]
    elif media_content_type == BrowsableMedia.CURRENT_USER_TOP_TRACKS:
        if top_tracks := await spotify.get_top_tracks():
            items = [_get_track_item_payload(track) for track in top_tracks]
    elif media_content_type == BrowsableMedia.NEW_RELEASES:
        if new_releases := await spotify.get_new_releases():
            items = [_get_album_item_payload(album) for album in new_releases]
    elif media_content_type == MediaType.PLAYLIST:
        if playlist := await spotify.get_playlist(media_content_id):
            title = playlist.name
            image = playlist.images[0].url if playlist.images else None
            for playlist_item in playlist.tracks.items:
                if playlist_item.track.type is ItemType.TRACK:
                    if TYPE_CHECKING:
                        assert isinstance(playlist_item.track, Track)
                    items.append(_get_track_item_payload(playlist_item.track))
                elif playlist_item.track.type is ItemType.EPISODE:
                    if TYPE_CHECKING:
                        assert isinstance(playlist_item.track, SimplifiedEpisode)
                    items.append(_get_episode_item_payload(playlist_item.track))
    elif media_content_type == MediaType.ALBUM:
        if album := await spotify.get_album(media_content_id):
            title = album.name
            image = album.images[0].url if album.images else None
            items = [
                _get_track_item_payload(track, show_thumbnails=False)
                for track in album.tracks
            ]
    elif media_content_type == MediaType.ARTIST:
        if (artist_albums := await spotify.get_artist_albums(media_content_id)) and (
            artist := await spotify.get_artist(media_content_id)
        ):
            title = artist.name
            image = artist.images[0].url if artist.images else None
            items = [_get_album_item_payload(album) for album in artist_albums]
    elif media_content_type == MEDIA_TYPE_SHOW:
        if (show_episodes := await spotify.get_show_episodes(media_content_id)) and (
            show := await spotify.get_show(media_content_id)
        ):
            title = show.name
            image = show.images[0].url if show.images else None
            items = [_get_episode_item_payload(episode) for episode in show_episodes]

    try:
        media_class = CONTENT_TYPE_MEDIA_CLASS[media_content_type]
    except KeyError:
        _LOGGER.debug("Unknown media type received: %s", media_content_type)
        return None

    if title is None:
        title = LIBRARY_MAP.get(media_content_id, "Unknown")

    can_play = media_content_type in PLAYABLE_MEDIA_TYPES and (
        media_content_type != MediaType.ARTIST or can_play_artist
    )

    if TYPE_CHECKING:
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
