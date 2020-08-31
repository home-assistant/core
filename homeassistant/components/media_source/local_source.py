"""Local Media Source Implementation."""
import datetime as dt
import mimetypes
from pathlib import Path
from typing import Tuple

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import sanitize_path

from .const import DOMAIN, MEDIA_MIME_TYPES
from .models import BrowseMedia, MediaSource, MediaSourceItem, PlayMedia


@callback
def async_setup(hass: HomeAssistant):
    """Set up local media source."""
    source = LocalSource(hass)
    hass.data[DOMAIN][DOMAIN] = source
    hass.http.register_view(LocalMediaView(hass, source))


class LocalSource(MediaSource):
    """Provide local directories as media sources."""

    def __init__(self, hass: HomeAssistant):
        """Initialize local source."""
        super().__init__(DOMAIN)
        self.hass = hass

    @callback
    def async_parse_identifier(self, item: MediaSourceItem):
        """Parse identifier."""
        if item.identifier == "":
            source_dir_id = "media"
            location = ""

        else:
            source_dir_id, location = item.identifier.split("/", 1)

        if source_dir_id != "media":
            raise Unresolvable("Unknown source directory.")

        if location != sanitize_path(location):
            raise Unresolvable("Invalid path.")

        return source_dir_id, location

    @callback
    def async_full_path(self, source_dir_id, location) -> Path:
        """Return full path."""
        return self.hass.config.path("media", location)

    async def async_resolve_media(self, item: MediaSourceItem) -> str:
        """Resolve media to a url."""
        source_dir_id, location = self.async_parse_identifier(item)
        mime_type, _ = await self.hass.async_add_executor_job(
            mimetypes.guess_type, self.async_full_path(source_dir_id, location)
        )
        return PlayMedia(f"/media/{item.identifier}", mime_type)

    async def async_browse_media(
        self, item: MediaSourceItem, media_types: Tuple[str]
    ) -> BrowseMedia:
        """Return media."""
        try:
            source_dir_id, location = self.async_parse_identifier(item)
        except Unresolvable as err:
            raise BrowseError(str(err))

        return await self.hass.async_add_executor_job(
            self._browse_media, source_dir_id, location
        )

    def _browse_media(self, source_dir_id, location):
        """Browse media."""
        full_path = Path(self.hass.config.path("media", location))

        if not full_path.exists():
            raise BrowseError("Path does not exist in.")

        if not full_path.is_dir():
            raise BrowseError("Path is not a directory.")

        return self._build_item_response(source_dir_id, full_path)

    def _build_item_response(self, source_dir_id: str, path: Path, is_child=False):
        mime_type, _ = mimetypes.guess_type(str(path))
        media = BrowseMedia(
            DOMAIN,
            f"{source_dir_id}/{path.relative_to(self.hass.config.path('media'))}",
            path.name,
            mime_type,
        )
        media.can_play = path.is_file()
        media.can_expand = path.is_dir()

        # Make sure it's a file or directory
        if not media.can_play and not media.can_expand:
            return None

        # Stat Results
        stat = path.stat()
        media.created = dt.datetime.fromtimestamp(stat.st_ctime)
        media.modified = dt.datetime.fromtimestamp(stat.st_mtime)

        # Check that it's a media file
        if media.can_play and (
            not mime_type or mime_type.split("/")[0] not in MEDIA_MIME_TYPES
        ):
            return None

        if not media.can_expand:
            return media

        media.name += "/"

        # Append first level children
        if not is_child:
            media.children = []
            for child_path in path.iterdir():
                child = self._build_item_response(child_path, True)
                if child:
                    media.children.append(child)

        return media


class LocalMediaView(HomeAssistantView):
    """
    Local Media Finder View.

    Returns media files in config/media.
    """

    url = "/media/{identifier:.*}"
    name = "media"

    def __init__(self, hass: HomeAssistant, source: LocalSource):
        """Initialize the media view."""
        self.hass = hass
        self.source = source

    async def get(self, request: web.Request, identifier: str) -> web.FileResponse:
        """Start a GET request."""
        try:
            source_dir_id, location = self.source.async_parse_identifier(identifier)
        except Unresolvable:
            raise web.HTTPNotFound()

        media_path = self.source.full_path(source_dir_id, location)

        # Check that the file exists
        if not media_path.is_file():
            raise web.HTTPNotFound()

        # Check that it's a media file
        mime_type, _ = await request.app["hass"].async_add_executor_job(
            mimetypes.guess_type, media_path
        )
        if not mime_type or mime_type.split("/")[0] not in MEDIA_MIME_TYPES:
            raise web.HTTPNotFound()

        return web.FileResponse(media_path)
