"""Local Media Source Implementation."""
import datetime as dt
import mimetypes
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.static import CACHE_HEADERS
from homeassistant.core import HomeAssistant

from .const import DOMAIN, MEDIA_MIME_TYPES, URI_SCHEME
from .models import Media


async def async_setup_media_source(hass: HomeAssistant):
    """Set up local media source."""
    hass.http.register_view(LocalMediaView(hass))
    return ("local", async_find_media)


async def async_find_media(hass: HomeAssistant, location=None) -> Media:
    """Return media."""

    def build_item_response(path: Path, is_child=False):
        mime_type, _ = mimetypes.guess_type(str(path))
        location = str(path)[len(hass.config.config_dir) :]

        media = Media(DOMAIN, path.name, f"{URI_SCHEME}local{location}", mime_type)
        media.is_file = path.is_file()
        media.is_dir = path.is_dir()

        # Make sure it's a file or directory
        if not media.is_file and not media.is_dir:
            return None

        # Stat Results
        stat = path.stat()
        media.created = dt.datetime.fromtimestamp(stat.st_ctime)
        media.modified = dt.datetime.fromtimestamp(stat.st_mtime)

        # Check that it's a media file
        if media.is_file and (
            not mime_type or mime_type.split("/")[0] not in MEDIA_MIME_TYPES
        ):
            return None

        if media.is_dir:
            media.name += "/"
            # Append first level children
            if not is_child:
                media.children = []
                for child_path in path.iterdir():
                    child = build_item_response(child_path, True)
                    if child:
                        media.children.append(child)

        return media

    if not location:
        # Default to config/media
        location = hass.config.path("media")
    else:
        # Prepend config directory
        location = hass.config.path(location[1:])

    return await hass.async_add_executor_job(build_item_response, Path(location))


class LocalMediaView(HomeAssistantView):
    """
    Local Media Finder View.

    Returns media files in config/media.
    """

    url = "/media/{path:.*}"
    name = "media"

    def __init__(self, hass: HomeAssistant):
        """Initialize the media view."""
        self.hass = hass
        super().__init__()

    async def get(self, request: web.Request, path: str) -> web.FileResponse:
        """Start a GET request."""

        base_path = self.hass.config.path("media")
        media_path = Path(f"{base_path}/{path}")

        # Check that the file exists
        if not media_path.is_file():
            raise web.HTTPNotFound()

        # Check that it's a media file
        mime_type, _ = mimetypes.guess_type(str(media_path))
        if not mime_type or mime_type.split("/")[0] not in MEDIA_MIME_TYPES:
            raise web.HTTPNotFound()

        return web.FileResponse(media_path, headers=CACHE_HEADERS)
