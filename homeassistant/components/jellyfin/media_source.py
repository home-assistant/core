"""The Media Source implementation for the Jellyfin integration."""
import logging
import mimetypes
from typing import List

from jellyfin_apiclient_python.api import jellyfin_url
from jellyfin_apiclient_python.client import JellyfinClient

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_TRACK,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant

from .const import (  # pylint:disable=unused-import
    COLLECTION_TYPE_MUSIC,
    DATA_CLIENT,
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
    ITEM_TYPE_LIBRARY,
    MAX_STREAMING_BITRATE,
    MEDIA_SOURCE_KEY_PATH,
    MEDIA_TYPE_AUDIO,
    SUPPORTED_COLLECTION_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_get_media_source(hass: HomeAssistant):
    """Set up Jellyfin media source."""

    """Currently only a single Jellyfin server is supported"""
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    data = hass.data[DOMAIN][entry.entry_id]
    client = data[DATA_CLIENT]

    return JellyfinSource(hass, client)


class JellyfinSource(MediaSource):
    """Represents a Jellyfin server."""

    name: str = "Jellyfin"

    def __init__(self, hass: HomeAssistant, client: JellyfinClient):
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
        elif item_type == ITEM_TYPE_ARTIST:
            return await self._build_artist(media_item, True)
        elif item_type == ITEM_TYPE_ALBUM:
            return await self._build_album(media_item, True)
        else:
            raise BrowseError("Unsupported item type %s" % item_type)

    async def _build_libraries(self) -> BrowseMediaSource:
        """Return all supported libraries the user has access to as media sources."""
        base = BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=None,
            title=self.name,
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_DIRECTORY,
        )

        libraries = await self._get_libraries()

        base.children = []

        for library in libraries:
            base.children.append(await self._build_library(library, False))

        return base

    async def _get_libraries(self) -> List[dict]:
        """Return all supported libraries a user has access to."""
        response = await self.hass.async_add_executor_job(self.api.get_media_folders)
        libraries = response["Items"]
        result = []
        for library in libraries:
            if library[ITEM_KEY_COLLECTION_TYPE] in SUPPORTED_COLLECTION_TYPES:
                result.append(library)
        return result

    async def _build_library(
        self, library: dict, include_children: bool
    ) -> BrowseMediaSource:
        """Return a single library as a browsable media source."""
        collection_type = library[ITEM_KEY_COLLECTION_TYPE]

        if collection_type == COLLECTION_TYPE_MUSIC:
            return await self._build_music_library(library, include_children)
        else:
            raise BrowseError("Unsupported collection type %s" % collection_type)

    async def _build_music_library(
        self, library: dict, include_children: bool
    ) -> BrowseMediaSource:
        """Return a single music library as a browsable media source."""
        id = library[ITEM_KEY_ID]
        name = library[ITEM_KEY_NAME]

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=id,
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=None,
            title=name,
            can_play=False,
            can_expand=True,
        )

        if include_children:
            result.children_media_class = MEDIA_CLASS_ARTIST
            result.children = await self._build_artists(id)

        return result

    async def _build_artists(self, library_id: str) -> List[BrowseMediaSource]:
        """Return all artists in the music library."""
        artists = await self._get_children(library_id, ITEM_TYPE_ARTIST)
        artists = sorted(artists, key=lambda k: k[ITEM_KEY_NAME])
        return [await self._build_artist(artist, False) for artist in artists]

    async def _build_artist(
        self, artist: dict, include_children: bool
    ) -> BrowseMediaSource:
        """Return a single artist as a browsable media source."""
        id = artist[ITEM_KEY_ID]
        title = artist[ITEM_KEY_NAME]
        thumbnail_url = self._get_thumbnail_url(artist)

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=id,
            media_class=MEDIA_CLASS_ARTIST,
            media_content_type=None,
            title=title,
            can_play=False,
            can_expand=True,
            thumbnail=thumbnail_url,
        )

        if include_children:
            result.children_media_class = MEDIA_CLASS_ALBUM
            result.children = await self._build_albums(id)

        return result

    async def _build_albums(self, artist_id: str) -> List[BrowseMediaSource]:
        """Return all albums of a single artist as browsable media sources."""
        albums = await self._get_children(artist_id, ITEM_TYPE_ALBUM)
        albums = sorted(albums, key=lambda k: k[ITEM_KEY_NAME])
        return [await self._build_album(album, False) for album in albums]

    async def _build_album(
        self, album: dict, include_children: bool
    ) -> BrowseMediaSource:
        """Return a single album as a browsable media source."""
        id = album[ITEM_KEY_ID]
        title = album[ITEM_KEY_NAME]
        thumbnail_url = self._get_thumbnail_url(album)

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=id,
            media_class=MEDIA_CLASS_ALBUM,
            media_content_type=None,
            title=title,
            can_play=False,
            can_expand=True,
            thumbnail=thumbnail_url,
        )

        if include_children:
            result.children_media_class = MEDIA_CLASS_TRACK
            result.children = await self._build_tracks(id)

        return result

    async def _build_tracks(self, album_id: str) -> List[BrowseMediaSource]:
        """Return all tracks of a single album as browsable media sources."""
        tracks = await self._get_children(album_id, ITEM_TYPE_AUDIO)
        tracks = sorted(tracks, key=lambda k: k[ITEM_KEY_INDEX_NUMBER])
        return [self._build_track(track) for track in tracks]

    def _build_track(self, track: dict) -> BrowseMediaSource:
        """Return a single track as a browsable media source."""
        id = track[ITEM_KEY_ID]
        title = track[ITEM_KEY_NAME]
        mime_type = _media_mime_type(track)
        thumbnail_url = self._get_thumbnail_url(track)

        result = BrowseMediaSource(
            domain=DOMAIN,
            identifier=id,
            media_class=MEDIA_CLASS_TRACK,
            media_content_type=mime_type,
            title=title,
            can_play=True,
            can_expand=False,
            thumbnail=thumbnail_url,
        )

        return result

    async def _get_children(self, parent_id: str, item_type=None) -> List[dict]:
        """Return all children for the parent_id whos item type is item_type."""
        params = {"Recursive": "true", "ParentId": parent_id}
        if item_type:
            params["IncludeItemTypes"] = item_type
            if item_type == ITEM_TYPE_AUDIO:
                params["Fields"] = ITEM_KEY_MEDIA_SOURCES

        result = await self.hass.async_add_executor_job(self.api.user_items, "", params)
        return result["Items"]

    def _get_thumbnail_url(self, media_item: dict) -> str:
        """Return the URL for the primary image of a media item if available."""
        id = media_item[ITEM_KEY_ID]
        image_tags = media_item[ITEM_KEY_IMAGE_TAGS]
        api_key = self.client.config.data["auth.token"]

        if "Primary" in image_tags:
            tag = image_tags["Primary"]
            return f"{self.url}Items/{id}/Images/Primary?Tag={tag}&api_key={api_key}"

    def _get_stream_url(self, media_item: dict) -> str:
        """Return the stream URL for a media item."""
        media_type = media_item[ITEM_KEY_MEDIA_TYPE]

        if media_type == MEDIA_TYPE_AUDIO:
            return self._get_audio_stream_url(media_item)
        else:
            raise BrowseError("Unsupported media type %s" % media_type)

    def _get_audio_stream_url(self, media_item: dict) -> str:
        """Return the stream URL for a music media item."""
        id = media_item[ITEM_KEY_ID]
        user_id = self.client.config.data["auth.user_id"]
        device_id = self.client.config.data["app.device_id"]
        api_key = self.client.config.data["auth.token"]

        return f"{self.url}Audio/{id}/universal?UserId={user_id}&DeviceId={device_id}&api_key={api_key}&MaxStreamingBitrate={MAX_STREAMING_BITRATE}"


def _media_mime_type(media_item: dict) -> str:
    """Return the mime type of a media item."""
    media_source = media_item[ITEM_KEY_MEDIA_SOURCES][0]
    path = media_source[MEDIA_SOURCE_KEY_PATH]
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type
