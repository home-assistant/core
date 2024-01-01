"""The Media Source implementation for the Jellyfin integration."""
from __future__ import annotations

import logging
import mimetypes
import os
from typing import Any

from jellyfin_apiclient_python.api import jellyfin_url
from jellyfin_apiclient_python.client import JellyfinClient

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant

from .const import (
    COLLECTION_TYPE_MOVIES,
    COLLECTION_TYPE_MUSIC,
    DOMAIN,
    ITEM_KEY_COLLECTION_TYPE,
    ITEM_KEY_ID,
    ITEM_KEY_IMAGE_TAGS,
    ITEM_KEY_INDEX_NUMBER,
    ITEM_KEY_MEDIA_SOURCES,
    ITEM_KEY_MEDIA_TYPE,
    ITEM_KEY_NAME,
    ITEM_TYPE_ALBUM,
    ITEM_TYPE_ARTIST,
    ITEM_TYPE_AUDIO,
    ITEM_TYPE_EPISODE,
    ITEM_TYPE_LIBRARY,
    ITEM_TYPE_MOVIE,
    ITEM_TYPE_SEASON,
    ITEM_TYPE_SERIES,
    MAX_IMAGE_WIDTH,
    MEDIA_SOURCE_KEY_PATH,
    MEDIA_TYPE_AUDIO,
    MEDIA_TYPE_NONE,
    MEDIA_TYPE_VIDEO,
    PLAYABLE_ITEM_TYPES,
    SUPPORTED_COLLECTION_TYPES,
)
from .models import JellyfinData

_LOGGER = logging.getLogger(__name__)


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Jellyfin media source."""
    # Currently only a single Jellyfin server is supported
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    jellyfin_data: JellyfinData = hass.data[DOMAIN][entry.entry_id]

    return JellyfinSource(hass, jellyfin_data.jellyfin_client)


class JellyfinSource(MediaSource):
    """Represents a Jellyfin server."""

    name: str = "Jellyfin"

    def __init__(self, hass: HomeAssistant, client: JellyfinClient) -> None:
        """Initialize the Jellyfin media source."""
        super().__init__(DOMAIN)

        self.hass = hass

        self.client = client
        self.api = client.jellyfin
        self.url = jellyfin_url(client, "")

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Return a streamable URL and associated mime type."""
        media_item = await self.hass.async_add_executor_job(
            self.api.get_item, item.identifier
        )

        stream_url = self._get_stream_url(media_item)
        mime_type = _media_mime_type(media_item)

        # Media Sources without a mime type have been filtered out during library creation
        assert mime_type is not None

        return PlayMedia(stream_url, mime_type)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return a browsable Jellyfin media source."""
        if not item.identifier:
            return await self._build_libraries()

        media_item = await self.hass.async_add_executor_job(
            self.api.get_item, item.identifier
        )

        item_type = media_item["Type"]
        if item_type == ITEM_TYPE_LIBRARY:
            return await self._build_library(media_item, True)
        if item_type == ITEM_TYPE_ARTIST:
            return await self._build_artist(media_item, True)
        if item_type == ITEM_TYPE_ALBUM:
            return await self._build_album(media_item, True)
        if item_type == ITEM_TYPE_SERIES:
            return await self._build_series(media_item, True)
        if item_type == ITEM_TYPE_SEASON:
            return await self._build_season(media_item, True)

        raise BrowseError(f"Unsupported item type {item_type}")

    async def _build_libraries(self) -> BrowseMediaSource:
        """Return all supported libraries the user has access to as media sources."""
        base = BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MEDIA_TYPE_NONE,
            title=self.name,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
        )

        libraries = await self._get_libraries()

        base.children = []

        for library in libraries:
            base.children.append(await self._build_library(library, False))

        return base

    async def _get_libraries(self) -> list[dict[str, Any]]:
        """Return all supported libraries a user has access to."""
        response = await self.hass.async_add_executor_job(self.api.get_media_folders)
        libraries = response["Items"]
        result = []
        for library in libraries:
            if ITEM_KEY_COLLECTION_TYPE in library:
                if library[ITEM_KEY_COLLECTION_TYPE] in SUPPORTED_COLLECTION_TYPES:
                    result.append(library)
        return result

    async def _build_library(
        self, library: dict[str, Any], include_children: bool
    ) -> BrowseMediaSource:
        """Return a single library as a browsable media source."""
        collection_type = library[ITEM_KEY_COLLECTION_TYPE]

        if collection_type == COLLECTION_TYPE_MUSIC:
            return await self._build_music_library(library, include_children)
        if collection_type == COLLECTION_TYPE_MOVIES:
            return await self._build_movie_library(library, include_children)
        return await self._build_tv_library(library, include_children)

    async def _build_music_library(
        self, library: dict[str, Any], include_children: bool
    ) -> BrowseMediaSource:
        """Return a single music library as a browsable media source."""
        library_id = library[ITEM_KEY_ID]
        library_name = library[ITEM_KEY_NAME]

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=library_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MEDIA_TYPE_NONE,
            title=library_name,
            can_play=False,
            can_expand=True,
        )

        if include_children:
            result.children_media_class = MediaClass.ARTIST
            result.children = await self._build_artists(library_id)
            if not result.children:
                result.children_media_class = MediaClass.ALBUM
                result.children = await self._build_albums(library_id)

        return result

    async def _build_artists(self, library_id: str) -> list[BrowseMediaSource]:
        """Return all artists in the music library."""
        artists = await self._get_children(library_id, ITEM_TYPE_ARTIST)
        artists = sorted(
            artists,
            # Sort by whether an artist has an name first, then by name
            # This allows for sorting artists with, without and with missing names
            key=lambda k: (
                ITEM_KEY_NAME not in k,
                k.get(ITEM_KEY_NAME),
            ),
        )
        return [await self._build_artist(artist, False) for artist in artists]

    async def _build_artist(
        self, artist: dict[str, Any], include_children: bool
    ) -> BrowseMediaSource:
        """Return a single artist as a browsable media source."""
        artist_id = artist[ITEM_KEY_ID]
        artist_name = artist[ITEM_KEY_NAME]
        thumbnail_url = self._get_thumbnail_url(artist)

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=artist_id,
            media_class=MediaClass.ARTIST,
            media_content_type=MEDIA_TYPE_NONE,
            title=artist_name,
            can_play=False,
            can_expand=True,
            thumbnail=thumbnail_url,
        )

        if include_children:
            result.children_media_class = MediaClass.ALBUM
            result.children = await self._build_albums(artist_id)

        return result

    async def _build_albums(self, parent_id: str) -> list[BrowseMediaSource]:
        """Return all albums of a single artist as browsable media sources."""
        albums = await self._get_children(parent_id, ITEM_TYPE_ALBUM)
        albums = sorted(
            albums,
            # Sort by whether an album has an name first, then by name
            # This allows for sorting albums with, without and with missing names
            key=lambda k: (
                ITEM_KEY_NAME not in k,
                k.get(ITEM_KEY_NAME),
            ),
        )
        return [await self._build_album(album, False) for album in albums]

    async def _build_album(
        self, album: dict[str, Any], include_children: bool
    ) -> BrowseMediaSource:
        """Return a single album as a browsable media source."""
        album_id = album[ITEM_KEY_ID]
        album_title = album[ITEM_KEY_NAME]
        thumbnail_url = self._get_thumbnail_url(album)

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=album_id,
            media_class=MediaClass.ALBUM,
            media_content_type=MEDIA_TYPE_NONE,
            title=album_title,
            can_play=False,
            can_expand=True,
            thumbnail=thumbnail_url,
        )

        if include_children:
            result.children_media_class = MediaClass.TRACK
            result.children = await self._build_tracks(album_id)

        return result

    async def _build_tracks(self, album_id: str) -> list[BrowseMediaSource]:
        """Return all tracks of a single album as browsable media sources."""
        tracks = await self._get_children(album_id, ITEM_TYPE_AUDIO)
        tracks = sorted(
            tracks,
            # Sort by whether a track has an index first, then by index
            # This allows for sorting tracks with, without and with missing indices
            key=lambda k: (
                ITEM_KEY_INDEX_NUMBER not in k,
                k.get(ITEM_KEY_INDEX_NUMBER),
            ),
        )
        return [
            self._build_track(track)
            for track in tracks
            if _media_mime_type(track) is not None
        ]

    def _build_track(self, track: dict[str, Any]) -> BrowseMediaSource:
        """Return a single track as a browsable media source."""
        track_id = track[ITEM_KEY_ID]
        track_title = track[ITEM_KEY_NAME]
        mime_type = _media_mime_type(track)
        thumbnail_url = self._get_thumbnail_url(track)

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=track_id,
            media_class=MediaClass.TRACK,
            media_content_type=mime_type,
            title=track_title,
            can_play=True,
            can_expand=False,
            thumbnail=thumbnail_url,
        )

        return result

    async def _build_movie_library(
        self, library: dict[str, Any], include_children: bool
    ) -> BrowseMediaSource:
        """Return a single movie library as a browsable media source."""
        library_id = library[ITEM_KEY_ID]
        library_name = library[ITEM_KEY_NAME]

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=library_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MEDIA_TYPE_NONE,
            title=library_name,
            can_play=False,
            can_expand=True,
        )

        if include_children:
            result.children_media_class = MediaClass.MOVIE
            result.children = await self._build_movies(library_id)

        return result

    async def _build_movies(self, library_id: str) -> list[BrowseMediaSource]:
        """Return all movies in the movie library."""
        movies = await self._get_children(library_id, ITEM_TYPE_MOVIE)
        movies = sorted(
            movies,
            # Sort by whether a movies has an name first, then by name
            # This allows for sorting moveis with, without and with missing names
            key=lambda k: (
                ITEM_KEY_NAME not in k,
                k.get(ITEM_KEY_NAME),
            ),
        )
        return [
            self._build_movie(movie)
            for movie in movies
            if _media_mime_type(movie) is not None
        ]

    def _build_movie(self, movie: dict[str, Any]) -> BrowseMediaSource:
        """Return a single movie as a browsable media source."""
        movie_id = movie[ITEM_KEY_ID]
        movie_title = movie[ITEM_KEY_NAME]
        mime_type = _media_mime_type(movie)
        thumbnail_url = self._get_thumbnail_url(movie)

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=movie_id,
            media_class=MediaClass.MOVIE,
            media_content_type=mime_type,
            title=movie_title,
            can_play=True,
            can_expand=False,
            thumbnail=thumbnail_url,
        )

        return result

    async def _build_tv_library(
        self, library: dict[str, Any], include_children: bool
    ) -> BrowseMediaSource:
        """Return a single tv show library as a browsable media source."""
        library_id = library[ITEM_KEY_ID]
        library_name = library[ITEM_KEY_NAME]

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=library_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MEDIA_TYPE_NONE,
            title=library_name,
            can_play=False,
            can_expand=True,
        )

        if include_children:
            result.children_media_class = MediaClass.TV_SHOW
            result.children = await self._build_tvshow(library_id)

        return result

    async def _build_tvshow(self, library_id: str) -> list[BrowseMediaSource]:
        """Return all series in the tv library."""
        series = await self._get_children(library_id, ITEM_TYPE_SERIES)
        series = sorted(
            series,
            # Sort by whether a seroes has an name first, then by name
            # This allows for sorting series with, without and with missing names
            key=lambda k: (
                ITEM_KEY_NAME not in k,
                k.get(ITEM_KEY_NAME),
            ),
        )
        return [await self._build_series(serie, False) for serie in series]

    async def _build_series(
        self, series: dict[str, Any], include_children: bool
    ) -> BrowseMediaSource:
        """Return a single series as a browsable media source."""
        series_id = series[ITEM_KEY_ID]
        series_title = series[ITEM_KEY_NAME]
        thumbnail_url = self._get_thumbnail_url(series)

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=series_id,
            media_class=MediaClass.TV_SHOW,
            media_content_type=MEDIA_TYPE_NONE,
            title=series_title,
            can_play=False,
            can_expand=True,
            thumbnail=thumbnail_url,
        )

        if include_children:
            result.children_media_class = MediaClass.SEASON
            result.children = await self._build_seasons(series_id)

        return result

    async def _build_seasons(self, series_id: str) -> list[BrowseMediaSource]:
        """Return all seasons in the series."""
        seasons = await self._get_children(series_id, ITEM_TYPE_SEASON)
        seasons = sorted(
            seasons,
            # Sort by whether a season has an index first, then by index
            # This allows for sorting seasons with, without and with missing indices
            key=lambda k: (
                ITEM_KEY_INDEX_NUMBER not in k,
                k.get(ITEM_KEY_INDEX_NUMBER),
            ),
        )
        return [await self._build_season(season, False) for season in seasons]

    async def _build_season(
        self, season: dict[str, Any], include_children: bool
    ) -> BrowseMediaSource:
        """Return a single series as a browsable media source."""
        season_id = season[ITEM_KEY_ID]
        season_title = season[ITEM_KEY_NAME]
        thumbnail_url = self._get_thumbnail_url(season)

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=season_id,
            media_class=MediaClass.TV_SHOW,
            media_content_type=MEDIA_TYPE_NONE,
            title=season_title,
            can_play=False,
            can_expand=True,
            thumbnail=thumbnail_url,
        )

        if include_children:
            result.children_media_class = MediaClass.EPISODE
            result.children = await self._build_episodes(season_id)

        return result

    async def _build_episodes(self, season_id: str) -> list[BrowseMediaSource]:
        """Return all episode in the season."""
        episodes = await self._get_children(season_id, ITEM_TYPE_EPISODE)
        episodes = sorted(
            episodes,
            # Sort by whether an episode has an index first, then by index
            # This allows for sorting episodes with, without and with missing indices
            key=lambda k: (
                ITEM_KEY_INDEX_NUMBER not in k,
                k.get(ITEM_KEY_INDEX_NUMBER),
            ),
        )
        return [
            self._build_episode(episode)
            for episode in episodes
            if _media_mime_type(episode) is not None
        ]

    def _build_episode(self, episode: dict[str, Any]) -> BrowseMediaSource:
        """Return a single episode as a browsable media source."""
        episode_id = episode[ITEM_KEY_ID]
        episode_title = episode[ITEM_KEY_NAME]
        mime_type = _media_mime_type(episode)
        thumbnail_url = self._get_thumbnail_url(episode)

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=episode_id,
            media_class=MediaClass.EPISODE,
            media_content_type=mime_type,
            title=episode_title,
            can_play=True,
            can_expand=False,
            thumbnail=thumbnail_url,
        )

        return result

    async def _get_children(
        self, parent_id: str, item_type: str
    ) -> list[dict[str, Any]]:
        """Return all children for the parent_id whose item type is item_type."""
        params = {
            "Recursive": "true",
            "ParentId": parent_id,
            "IncludeItemTypes": item_type,
        }
        if item_type in PLAYABLE_ITEM_TYPES:
            params["Fields"] = ITEM_KEY_MEDIA_SOURCES

        result = await self.hass.async_add_executor_job(self.api.user_items, "", params)
        return result["Items"]  # type: ignore[no-any-return]

    def _get_thumbnail_url(self, media_item: dict[str, Any]) -> str | None:
        """Return the URL for the primary image of a media item if available."""
        image_tags = media_item[ITEM_KEY_IMAGE_TAGS]

        if "Primary" not in image_tags:
            return None

        item_id = media_item[ITEM_KEY_ID]
        return str(self.api.artwork(item_id, "Primary", MAX_IMAGE_WIDTH))

    def _get_stream_url(self, media_item: dict[str, Any]) -> str:
        """Return the stream URL for a media item."""
        media_type = media_item[ITEM_KEY_MEDIA_TYPE]
        item_id = media_item[ITEM_KEY_ID]

        if media_type == MEDIA_TYPE_AUDIO:
            return self.api.audio_url(item_id)  # type: ignore[no-any-return]
        if media_type == MEDIA_TYPE_VIDEO:
            return self.api.video_url(item_id)  # type: ignore[no-any-return]

        raise BrowseError(f"Unsupported media type {media_type}")


def _media_mime_type(media_item: dict[str, Any]) -> str | None:
    """Return the mime type of a media item."""
    if not media_item.get(ITEM_KEY_MEDIA_SOURCES):
        _LOGGER.debug("Unable to determine mime type for item without media source")
        return None

    media_source = media_item[ITEM_KEY_MEDIA_SOURCES][0]

    if MEDIA_SOURCE_KEY_PATH not in media_source:
        _LOGGER.debug("Unable to determine mime type for media source without path")
        return None

    path = media_source[MEDIA_SOURCE_KEY_PATH]
    mime_type, _ = mimetypes.guess_type(path)

    if mime_type is None:
        _LOGGER.debug(
            "Unable to determine mime type for path %s", os.path.basename(path)
        )

    return mime_type
