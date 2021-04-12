"""Local Media Source Implementation."""
from __future__ import annotations

import asyncio
from io import BytesIO
import logging
import mimetypes
from pathlib import Path
import urllib

from PIL import Image
from aiohttp import web
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from mutagen import File

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_IMAGE,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_VIDEO,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import raise_if_invalid_path

from .const import (
    DATA_FFMPEG,
    DOMAIN,
    MEDIA_CLASS_MAP,
    MEDIA_MIME_TYPES,
    THUMBNAIL_QUALITY,
    THUMBNAIL_SIZE,
)
from .models import BrowseMediaSource, MediaSource, MediaSourceItem, PlayMedia

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup(hass: HomeAssistant):
    """Set up local media source."""
    source = LocalSource(hass)
    hass.data[DOMAIN][DOMAIN] = source
    hass.http.register_view(LocalMediaView(hass, source))
    hass.http.register_view(LocalMediaThumbnailView(hass, source))


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
    def async_parse_identifier(self, item: MediaSourceItem) -> tuple[str, str]:
        """Parse identifier."""
        if not item.identifier:
            # Empty source_dir_id and location
            return "", ""

        source_dir_id, location = item.identifier.split("/", 1)
        if source_dir_id not in self.hass.config.media_dirs:
            raise Unresolvable("Unknown source directory.")

        try:
            raise_if_invalid_path(location)
        except ValueError as err:
            raise Unresolvable("Invalid path.") from err

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
        self, item: MediaSourceItem, media_types: tuple[str] = MEDIA_MIME_TYPES
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

        thumbnail = None
        if media_class in (MEDIA_CLASS_MUSIC, MEDIA_CLASS_IMAGE, MEDIA_CLASS_VIDEO):
            thumbnail = urllib.parse.quote(
                f"/media-thumb/{source_dir_id}/{path.relative_to(self.hass.config.media_dirs[source_dir_id])}"
            )

        media = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{source_dir_id}/{path.relative_to(self.hass.config.media_dirs[source_dir_id])}",
            media_class=media_class,
            media_content_type=mime_type or "",
            title=title,
            can_play=is_file,
            can_expand=is_dir,
            thumbnail=thumbnail,
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
        try:
            raise_if_invalid_path(location)
        except ValueError as err:
            raise web.HTTPBadRequest() from err

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


class LocalMediaThumbnailView(HomeAssistantView):
    """
    Local Media Finder View.

    Returns thumbnails of media files in config/media.
    """

    url = "/media-thumb/{source_dir_id}/{location:.*}"
    name = "media-thumb"
    requires_auth = False

    def __init__(self, hass: HomeAssistant, source: LocalSource):
        """Initialize the media view."""
        self.hass = hass
        self.source = source
        self._ffmpeg = hass.data[DATA_FFMPEG]

    async def get(
        self, request: web.Request, source_dir_id: str, location: str
    ) -> web.FileResponse:
        """Start a GET request."""
        try:
            raise_if_invalid_path(location)
        except ValueError as err:
            raise web.HTTPBadRequest() from err

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

        media_class = MEDIA_CLASS_MAP.get(
            mime_type and mime_type.split("/")[0], MEDIA_CLASS_DIRECTORY
        )

        img = await self.__get_image(media_class, media_path)

        if not img:
            raise web.HTTPNotFound()

        exif = b""
        # Get raw exif data for thumbnail (keep orientation and other info)
        if img.info:
            exif = img.info.get("exif", b"")

        img.thumbnail(THUMBNAIL_SIZE, Image.HAMMING)

        # Convert unsupported JPEG modes
        if img.mode not in ("RGB", "L", "CMYK"):
            img = img.convert("RGB")

        # save thumbnail to buffer
        data = BytesIO()
        img.save(data, format="jpeg", exif=exif, quality=THUMBNAIL_QUALITY)

        resp = web.StreamResponse(
            status=200,
            headers={"Cache-Control": "max-age=31536000", "Content-Type": "image/jpeg"},
        )

        await resp.prepare(request)
        await resp.write(data.getvalue())
        return resp

    async def __get_image(self, media_class, media_path):
        img = None

        if media_class == MEDIA_CLASS_IMAGE:
            try:
                img = Image.open(media_path)
            except OSError as err:
                _LOGGER.warning("Failed to create thumbnail for image '%s", media_path)
                raise ValueError() from err

        if media_class == MEDIA_CLASS_MUSIC:
            try:
                audio = File(media_path)
                apic = audio.tags.get("APIC:")
                if apic:
                    img = Image.open(BytesIO(apic.data))
            except OSError as err:
                _LOGGER.warning("Failed to create thumbnail for music '%s", media_path)
                raise ValueError() from err

        if media_class == MEDIA_CLASS_VIDEO:
            try:
                ffmpeg = ImageFrame(self._ffmpeg.binary)
                image = await asyncio.shield(
                    ffmpeg.get_image(media_path, output_format=IMAGE_JPEG)
                )
                if image:
                    img = Image.open(BytesIO(image))
            except OSError as err:
                _LOGGER.warning("Failed to create thumbnail for video '%s", media_path)
                raise ValueError() from err

        return img
