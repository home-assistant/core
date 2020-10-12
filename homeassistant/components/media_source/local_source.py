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

from .const import DOMAIN, MEDIA_CLASS_MAP, MEDIA_MIME_TYPES
from .models import BrowseMediaSource, MediaSource, MediaSourceItem, PlayMedia


@callback
def async_setup(hass: HomeAssistant):
    """Set up local media source."""
    source = LocalSource(hass)
    hass.data[DOMAIN][DOMAIN] = source
    hass.http.register_view(LocalMediaView(hass, source))


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
        return Path(self.hass.config.media_dirs[source_dir_id], location)

    @callback
    def async_parse_identifier(self, item: MediaSourceItem) -> Tuple[str, str]:
        """Parse identifier."""
        if not item.identifier:
            # Empty source_dir_id and location
            return "", ""

        source_dir_id, location = item.identifier.split("/", 1)
        if source_dir_id not in self.hass.config.media_dirs:
            raise Unresolvable("Unknown source directory.")

        if location != sanitize_path(location):
            raise Unresolvable("Invalid path.")

        return source_dir_id, location

    async def async_resolve_media(self, item: MediaSourceItem) -> str:
        """Resolve media to a url."""
        source_dir_id, location = self.async_parse_identifier(item)
        if source_dir_id == "" or source_dir_id not in self.hass.config.media_dirs:
            raise Unresolvable("Unknown source directory.")

        mime_type, _ = mimetypes.guess_type(
            str(self.async_full_path(source_dir_id, location))
        )
        return PlayMedia(f"/media/{item.identifier}", mime_type)

    async def async_browse_media(
        self, item: MediaSourceItem, media_types: Tuple[str] = MEDIA_MIME_TYPES
    ) -> BrowseMediaSource:
        """Return media."""
        try:
            source_dir_id, location = self.async_parse_identifier(item)
        except Unresolvable as err:
            raise BrowseError(str(err)) from err

        return await self.hass.async_add_executor_job(
            self._browse_media, source_dir_id, location
        )

    def _browse_media(self, source_dir_id: str, location: Path):
        """Browse media."""

        # If only one media dir is configured, use that as the local media root
        if source_dir_id == "" and len(self.hass.config.media_dirs) == 1:
            source_dir_id = list(self.hass.config.media_dirs)[0]

        # Multiple folder, root is requested
        if source_dir_id == "":
            if location:
                raise BrowseError("Folder not found.")

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

            base.children = [
                self._browse_media(source_dir_id, "")
                for source_dir_id in self.hass.config.media_dirs
            ]

            return base

        full_path = Path(self.hass.config.media_dirs[source_dir_id], location)

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

        media_class = MEDIA_CLASS_MAP.get(
            mime_type and mime_type.split("/")[0], MEDIA_CLASS_DIRECTORY
        )

        media = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{source_dir_id}/{path.relative_to(self.hass.config.media_dirs[source_dir_id])}",
            media_class=media_class,
            media_content_type=mime_type or "",
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

        # Sort children showing directories first, then by name
        media.children.sort(key=lambda child: (child.can_play, child.title))

        return media


class LocalMediaView(HomeAssistantView):
    """
    Local Media Finder View.

    Returns media files in config/media.
    """

    url = "/media/{source_dir_id}/{location:.*}"
    name = "media"

    def __init__(self, hass: HomeAssistant, source: LocalSource):
        """Initialize the media view."""
        self.hass = hass
        self.source = source

    async def get(
        self, request: web.Request, source_dir_id: str, location: str
    ) -> web.FileResponse:
        """Start a GET request."""
        if location != sanitize_path(location):
            raise web.HTTPNotFound()

        if source_dir_id not in self.hass.config.media_dirs:
            raise web.HTTPNotFound()

        media_path = self.source.async_full_path(source_dir_id, location)

        # Check that the file exists
        if not media_path.is_file():
            raise web.HTTPNotFound()

        # Check that it's a media file
        mime_type, _ = mimetypes.guess_type(str(media_path))
        if not mime_type or mime_type.split("/")[0] not in MEDIA_MIME_TYPES:
            raise web.HTTPNotFound()

        return web.FileResponse(media_path)
