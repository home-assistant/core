import logging
from typing import Tuple, List
from aiohttp import web
import mimetypes

from jellyfin_apiclient_python.client import JellyfinClient
from jellyfin_apiclient_python.api import jellyfin_url

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_MUSIC,
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
    SUPPORTED_COLLECTION_TYPES,
    COLLECTION_TYPE_MOVIES,
    COLLECTION_TYPE_TVSHOWS,
    COLLECTION_TYPE_MUSIC,
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
    hass.http.register_view(JellyfinMediaView(hass, source))

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


def _is_playable(item: dict) -> bool:
    if item["IsFolder"]:
        return False

    media_sources = item["MediaSources"]
    if len(media_sources) == 0:
        return False

    media_source = media_sources[0]
    if media_source["Type"] != "Default":
        return False

    return True


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
        _, item_id = parse_identifier(item)

        media_item = await self.hass.async_add_executor_job(self.api.get_item, item_id)

        stream_url = self._get_stream_url(media_item)
        mime_type = _media_mime_type(media_item)

        print(stream_url, mime_type)
        return PlayMedia(stream_url, mime_type)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        library_id, item_id = parse_identifier(item)

        if not library_id:
            return await self._build_libraries()

        library = await self.hass.async_add_executor_job(self.api.get_item, library_id)
        media_class = _media_class(library["CollectionType"])

        if not item_id:
            return await self._build_library(library, media_class)

        media_item = self.api.get_item(item_id)

        return self._processMediaItem(library_id, media_item, media_class)

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
            media_class = _media_class(library["CollectionType"])
            base.children.append(await self._build_library(library, media_class))

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
        self, library: dict, media_class: str
    ) -> BrowseMediaSource:
        id = library["Id"]
        name = library["Name"]

        _LOGGER.info(f"Bulding library {name} with media class {media_class}")

        librarySource = BrowseMediaSource(
            domain=DOMAIN,
            identifier=id,
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=None,
            title=name,
            can_play=False,
            can_expand=True,
            children_media_class=media_class,
        )

        library_members = await self._get_library_members(id)

        librarySource.children = []
        for library_member in library_members:
            if _is_playable(library_member):
                child = self._processMediaItem(id, library_member, media_class)
                librarySource.children.append(child)
        return librarySource

    async def _get_library_members(self, library_id: str) -> List[dict]:
        params = {"Recursive": "true", "ParentId": library_id, "Fields": "MediaSources"}

        result = await self.hass.async_add_executor_job(self.api.user_items, "", params)
        return result["Items"]

    def _processMediaItem(
        self, library_id: str, item: dict, media_class: str
    ) -> BrowseMediaSource:

        id = item["Id"]
        title = item["Name"]
        mime_type = _media_mime_type(item)

        media = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{library_id}~~{id}",
            media_class=media_class,
            media_content_type=mime_type,
            title=title,
            can_play=True,
            can_expand=False,
        )

        return media

    def _get_stream_url(self, media_item: dict) -> str:
        id = media_item["Id"]
        media_type = media_item["MediaType"]

        if media_type == "Video":
            return f"{self.url}/Videos/{id}/stream"
        else:
            return f"{self.url}/Audio/{id}/stream"


class JellyfinMediaView(HomeAssistantView):
    """
    View of Jellyfin Media

    Returns media files in Jellyfin libraries for configured user
    """

    name = "Jellyfin"
    url = "/media/jellyfin/{item_id}"

    def __init__(self, hass: HomeAssistant, source: JellyfinSource):
        """Initialize the media view."""
        self.hass = hass
        self.source = source

    async def get(self, request: web.Request, item_id: str) -> web.Response:
        url = f"{self.source.url}/Items/{item_id}/Download"
        return web.FileResponse(url)
