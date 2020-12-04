import logging
import mimetypes
from typing import Tuple

from jellyfin_apiclient_python.client import JellyfinClient
from jellyfin_apiclient_python.api import jellyfin_url

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_VIDEO,
    MEDIA_CLASS_IMAGE,
    MEDIA_TYPE_MOVIE,
)
from homeassistant.components.media_source.const import MEDIA_CLASS_MAP

from homeassistant.core import HomeAssistant

from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)

from .const import DATA_CLIENT, DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def async_get_media_source(hass: HomeAssistant):
    """Set up Jellyfin media source."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    data = hass.data[DOMAIN][entry.entry_id]
    client = data[DATA_CLIENT]

    return JellyfinSource(hass, client)


def parse_identifier(item: MediaSourceItem) -> Tuple[str, str]:
    identifier = item.identifier or ""
    start = ["", ""]
    items = identifier.lstrip("/").split("~~", 1)
    return tuple(items + start[len(items) :])


def _media_mime_type(media_class: str) -> str:
    if media_class == MEDIA_CLASS_VIDEO:
        return "video"
    elif media_class == MEDIA_CLASS_MUSIC:
        return "audio"
    elif media_class == MEDIA_CLASS_IMAGE:
        return "image"
    else:
        raise BrowseError("Unsupported media mime type %s" % type)


def _media_class(collection_type: str) -> str:
    """ Takes a Jellyfin collection type and return the corresponding media class """
    if collection_type == "movies" or collection_type == "tvshows":
        return MEDIA_CLASS_VIDEO
    elif collection_type == "music":
        return MEDIA_CLASS_MUSIC
    else:
        raise BrowseError(f"Unsupported collection type {collection_type}")


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
        media_item = self.api.get_item(item.identifier)
        path = media_item["MediaStreams"][0]["Path"]
        mime_type, _ = mimetypes.guess_type(path)

        return PlayMedia(f"{self.url}/Items/{item.identifier}", mime_type)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        library, item_id = parse_identifier(item)

        if not library:
            return await self._build_libraries()

        if not item_id:
            result = self.api.get_item(library)
            return self._build_library(library, result["CollectionType"])

        library_item = self.api.get_item(library)
        media_item = self.api.get_item(item_id)
        media_class = _media_class(library_item["CollectionType"])
        return self._processMediaItem(library, media_item, media_class)

    async def _build_libraries(self):
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

        base.children = [
            await self._build_library(library["Id"], library["CollectionType"])
            for library in libraries
        ]

        return base

    async def _get_libraries(self):
        result = await self.hass.async_add_executor_job(self.api.get_media_folders)
        return result["Items"]

    async def _build_library(
        self, library: str, collection_type: str
    ) -> BrowseMediaSource:
        _LOGGER.info(
            f"Bulding library {library} with collection type {collection_type}"
        )

        children_media_class = _media_class(collection_type)

        librarySource = BrowseMediaSource(
            domain=DOMAIN,
            identifier=library,
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=None,
            title=library,
            can_play=False,
            can_expand=True,
            children_media_class=children_media_class,
        )

        result = await self.hass.async_add_executor_job(
            self.api.user_items, "", {"Recursive": "true", "ParentId": library}
        )
        items = result["Items"]

        librarySource.children = []
        for item in items:
            print(item)
            if not item["IsFolder"]:
                child = self._processMediaItem(library, item, children_media_class)
                librarySource.children.append(child)

        return librarySource

    def _processMediaItem(
        self, library: str, item: dict, media_class: str
    ) -> BrowseMediaSource:
        item_id = item["Id"]
        title = item["Name"]

        mime_type = _media_mime_type(media_class)

        media = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{library}~~{self.url}/Items/{item_id}",
            media_class=media_class,
            media_content_type=mime_type,
            title=title,
            can_play=True,
            can_expand=False,
        )

        return media


class JellyfinMediaView(HomeAssistantView):
    """
    View of Jellyfin Media

    Returns media files in Jellyfin libraries for configured user
    """

    def __init__(self, hass: HomeAssistant, source: JellyfinSource):
        """Initialize the media view."""
        self.hass = hass
        self.source = source