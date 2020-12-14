import logging
from typing import Tuple, List
import mimetypes

from jellyfin_apiclient_python.client import JellyfinClient
from jellyfin_apiclient_python.api import jellyfin_url

from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_TRACK,
    MEDIA_CLASS_VIDEO,
)

from homeassistant.core import HomeAssistant

from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)

from .const import (
    MAX_STREAMING_BITRATE,
    SUPPORTED_COLLECTION_TYPES,
    COLLECTION_TYPE_MOVIES,
    COLLECTION_TYPE_TVSHOWS,
    COLLECTION_TYPE_MUSIC,
    ITEM_TYPE_ALBUM,
    ITEM_TYPE_ARTIST,
    ITEM_TYPE_AUDIO,
    ITEM_TYPE_LIBRARY,
    MEDIA_TYPE_AUDIO,
    DATA_CLIENT,
    DOMAIN,
)  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def async_get_media_source(hass: HomeAssistant):
    """Set up Jellyfin media source."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    data = hass.data[DOMAIN][entry.entry_id]
    client = data[DATA_CLIENT]

    source = JellyfinSource(hass, client)
    # hass.http.register_view(JellyfinMediaView(hass, source))

    return source


def parse_identifier(item: MediaSourceItem) -> Tuple[str, str]:
    identifier = item.identifier or ""
    start = ["", ""]
    items = identifier.lstrip("/").split("~~", 1)
    return tuple(items + start[len(items) :])


def _media_mime_type(media_item: dict) -> str:
    media_source = media_item["MediaSources"][0]
    path = media_source["Path"]
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type


def _media_class(collection_type: str) -> str:
    """ Takes a Jellyfin collection type and return the corresponding media class """
    if (
        collection_type == COLLECTION_TYPE_MOVIES
        or collection_type == COLLECTION_TYPE_TVSHOWS
    ):
        return MEDIA_CLASS_VIDEO
    elif collection_type == COLLECTION_TYPE_MUSIC:
        return MEDIA_CLASS_MUSIC
    else:
        raise BrowseError("Unsupported collection type %s" % collection_type)


class JellyfinSource(MediaSource):
    """Represents a Jellyfin server"""

    name: str = "Jellyfin"

    def __init__(self, hass: HomeAssistant, client: JellyfinClient):
        super().__init__(DOMAIN)

        self.hass = hass

        self.client = client
        self.api = client.jellyfin
        self.url = jellyfin_url(client, "")

        server_id = client.auth.server_id
        self._name = client.auth.get_server_info(server_id)["Name"]

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        media_item = await self.hass.async_add_executor_job(
            self.api.get_item, item.identifier
        )

        stream_url = self._get_stream_url(media_item)
        mime_type = _media_mime_type(media_item)

        print(stream_url, mime_type)
        return PlayMedia(stream_url, mime_type)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
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
        base = BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
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

    async def _get_libraries(self):
        response = await self.hass.async_add_executor_job(self.api.get_media_folders)
        libraries = response["Items"]
        result = []
        for library in libraries:
            if library["CollectionType"] in SUPPORTED_COLLECTION_TYPES:
                result.append(library)
        return result

    async def _build_library(
        self, library: dict, include_children: bool
    ) -> BrowseMediaSource:
        media_class = _media_class(library["CollectionType"])

        if media_class == MEDIA_CLASS_MUSIC:
            return await self._build_music_library(library, include_children)
        else:
            raise BrowseError("Unsupported media class %s" % media_class)

    async def _build_music_library(
        self, library: dict, include_children: bool
    ) -> BrowseMediaSource:
        id = library["Id"]
        name = library["Name"]

        _LOGGER.info(f"Bulding library {name} with media class {MEDIA_CLASS_MUSIC}")

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

    async def _build_artists(self, library_id: str):
        artists = await self._get_children(library_id, ITEM_TYPE_ARTIST)
        artists = sorted(artists, key=lambda k: k["Name"])
        return [await self._build_artist(artist, False) for artist in artists]

    async def _build_artist(self, artist: dict, include_children: bool):
        id = artist["Id"]
        title = artist["Name"]
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

    async def _build_albums(self, artist_id: str):
        albums = await self._get_children(artist_id, ITEM_TYPE_ALBUM)
        albums = sorted(albums, key=lambda k: k["Name"])
        return [await self._build_album(album, False) for album in albums]

    async def _build_album(self, album: dict, include_children: bool):
        id = album["Id"]
        title = album["Name"]
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

    async def _build_tracks(self, artist_id: str):
        tracks = await self._get_children(artist_id, ITEM_TYPE_AUDIO)
        tracks = sorted(tracks, key=lambda k: k["IndexNumber"])
        return [self._build_track(track) for track in tracks]

    def _build_track(self, track: dict):
        id = track["Id"]
        title = track["Name"]
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
        params = {"Recursive": "true", "ParentId": parent_id}
        if item_type:
            params["IncludeItemTypes"] = item_type
            if item_type == ITEM_TYPE_AUDIO:
                params["Fields"] = "MediaSources"

        result = await self.hass.async_add_executor_job(self.api.user_items, "", params)
        return result["Items"]

    def _processMediaItem(
        self, library_id: str, item: dict, media_class: str
    ) -> BrowseMediaSource:

        id = item["Id"]
        title = item["Name"]
        mime_type = _media_mime_type(item)
        thumbnail_url = self._get_thumbnail_url(item)

        media = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{library_id}~~{id}",
            media_class=media_class,
            media_content_type=mime_type,
            title=title,
            can_play=True,
            can_expand=False,
            thumbnail=thumbnail_url,
        )

        return media

    def _get_thumbnail_url(self, media_item: dict) -> str:
        id = media_item["Id"]
        image_tags = media_item["ImageTags"]
        api_key = self.client.config.data["auth.token"]

        if "Primary" in image_tags:
            tag = image_tags["Primary"]
            return f"{self.url}Items/{id}/Images/Primary?Tag={tag}&api_key={api_key}"

    def _get_stream_url(self, media_item: dict) -> str:
        media_type = media_item["MediaType"]

        if media_type == MEDIA_TYPE_AUDIO:
            return self._get_audio_stream_url(media_item)
        else:
            raise BrowseError("Unsupported media type %s" % media_type)

    def _get_audio_stream_url(self, media_item: dict) -> str:
        id = media_item["Id"]
        user_id = self.client.config.data["auth.user_id"]
        device_id = self.client.config.data["app.device_id"]
        api_key = self.client.config.data["auth.token"]

        return f"{self.url}Audio/{id}/universal?UserId={user_id}&DeviceId={device_id}&api_key={api_key}&MaxStreamingBitrate={MAX_STREAMING_BITRATE}"