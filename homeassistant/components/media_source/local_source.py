"""Local Media Source Implementation."""
import mimetypes
from pathlib import Path
from typing import Tuple

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player.const import MEDIA_CLASS_DIRECTORY
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import sanitize_path

from .const import DOMAIN, MEDIA_MIME_TYPES
from .models import BrowseMediaSource, MediaSource, MediaSourceItem, PlayMedia


@callback
def async_setup(hass: HomeAssistant):
    """Set up local media source."""
    source = LocalSource(hass)
    hass.data[DOMAIN][DOMAIN] = source
    hass.http.register_view(LocalMediaView(hass))


@callback
def async_parse_identifier(item: MediaSourceItem) -> Tuple[str, str]:
    """Parse identifier."""
    if not item.identifier:
        source_dir_id = "media"
        location = ""

    else:
        source_dir_id, location = item.identifier.lstrip("/").split("/", 1)

    if source_dir_id != "media":
        raise Unresolvable("Unknown source directory.")

    if location != sanitize_path(location):
        raise Unresolvable("Invalid path.")

    return source_dir_id, location


class LocalSource(MediaSource):
    """Provide local directories as media sources."""

    name: str = "Local Media"

    def __init__(self, hass: HomeAssistant):
        """Initialize local source."""
        super().__init__(DOMAIN)
        self.hass = hass

    @callback
    def async_full_path(self, source_dir_id, location) -> Path:
        """Return full path."""
        return self.hass.config.path("media", location)

    async def async_resolve_media(self, item: MediaSourceItem) -> str:
        """Resolve media to a url."""
        source_dir_id, location = async_parse_identifier(item)
        mime_type, _ = mimetypes.guess_type(
            self.async_full_path(source_dir_id, location)
        )
        return PlayMedia(item.identifier, mime_type)

    async def async_browse_media(
        self, item: MediaSourceItem, media_types: Tuple[str] = MEDIA_MIME_TYPES
    ) -> BrowseMediaSource:
        """Return media."""
        try:
            source_dir_id, location = async_parse_identifier(item)
        except Unresolvable as err:
            raise BrowseError(str(err)) from err

        return await self.hass.async_add_executor_job(
            self._browse_media, source_dir_id, location
        )

    def _browse_media(self, source_dir_id, location):
        """Browse media."""
        full_path = Path(self.hass.config.path("media", location))

        if not full_path.exists():
            if location == "":
                raise BrowseError("Media directory does not exist.")
            raise BrowseError("Path does not exist.")

        if not full_path.is_dir():
            raise BrowseError("Path is not a directory.")

        return self._build_item_response(source_dir_id, full_path)

    def _build_item_response(self, source_dir_id: str, path: Path, is_child=False):
        mime_type, _ = mimetypes.guess_type(str(path))
        is_file = path.is_file()
        is_dir = path.is_dir()

        # Make sure it's a file or directory
        if not is_file and not is_dir:
            return None

        # Check that it's a media file
        if is_file and (
            not mime_type or mime_type.split("/")[0] not in MEDIA_MIME_TYPES
        ):
            return None

        title = path.name
        if is_dir:
            title += "/"

        media = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{source_dir_id}/{path.relative_to(self.hass.config.path('media'))}",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type="directory",
            title=title,
            can_play=is_file,
            can_expand=is_dir,
        )

        if is_file or is_child:
            return media

        # Append first level children
        media.children = []
        for child_path in path.iterdir():
            child = self._build_item_response(source_dir_id, child_path, True)
            if child:
                media.children.append(child)

        return media


class LocalMediaView(HomeAssistantView):
    """
    Local Media Finder View.

    Returns media files in config/media.
    """

    url = "/media/{location:.*}"
    name = "media"

    def __init__(self, hass: HomeAssistant):
        """Initialize the media view."""
        self.hass = hass

    async def get(self, request: web.Request, location: str) -> web.FileResponse:
        """Start a GET request."""
        if location != sanitize_path(location):
            return web.HTTPNotFound()

        media_path = Path(self.hass.config.path("media", location))

        # Check that the file exists
        if not media_path.is_file():
            raise web.HTTPNotFound()

        # Check that it's a media file
        mime_type, _ = mimetypes.guess_type(str(media_path))
        if not mime_type or mime_type.split("/")[0] not in MEDIA_MIME_TYPES:
            raise web.HTTPNotFound()

        return web.FileResponse(media_path)
