"""Local Media Source Implementation."""

from __future__ import annotations

import io
import logging
import mimetypes
from pathlib import Path
import shutil
from typing import Any, Protocol, cast

from aiohttp import web
from aiohttp.web_request import FileField
import voluptuous as vol

from homeassistant.components import http, websocket_api
from homeassistant.components.http import require_admin
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import raise_if_invalid_filename, raise_if_invalid_path

from .const import DOMAIN, MEDIA_CLASS_MAP, MEDIA_MIME_TYPES, MEDIA_SOURCE_DATA
from .error import Unresolvable
from .models import BrowseMediaSource, MediaSource, MediaSourceItem, PlayMedia

MAX_UPLOAD_SIZE = 1024 * 1024 * 10
LOGGER = logging.getLogger(__name__)


class PathNotSupportedError(HomeAssistantError):
    """Error to indicate a path is not supported."""


class InvalidFileNameError(HomeAssistantError):
    """Error to indicate an invalid file name."""


class UploadedFile(Protocol):
    """Protocol describing properties of an uploaded file."""

    filename: str
    file: io.IOBase
    content_type: str


async def async_get_media_source(hass: HomeAssistant) -> LocalSource:
    """Set up local media source."""
    return LocalSource(hass, DOMAIN, "My media", hass.config.media_dirs, "/media")


class LocalSource(MediaSource):
    """Provide local directories as media sources."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        name: str,
        media_dirs: dict[str, str],
        url_prefix: str,
    ) -> None:
        """Initialize local source."""
        super().__init__(domain)
        self.hass = hass
        self.name = name
        self.media_dirs = media_dirs
        self.url_prefix = url_prefix

    @callback
    def async_full_path(self, source_dir_id: str, location: str) -> Path:
        """Return full path."""
        base_path = self.media_dirs[source_dir_id]
        full_path = Path(base_path, location)
        full_path.relative_to(base_path)
        return full_path

    @callback
    def async_parse_identifier(self, item: MediaSourceItem) -> tuple[str, str]:
        """Parse identifier."""
        if item.domain != self.domain:
            raise Unresolvable("Unknown domain.")

        source_dir_id, _, location = item.identifier.partition("/")
        if source_dir_id not in self.media_dirs:
            raise Unresolvable("Unknown source directory.")

        try:
            raise_if_invalid_path(location)
        except ValueError as err:
            raise Unresolvable("Invalid path.") from err

        if Path(location).is_absolute():
            raise Unresolvable("Invalid path.")

        return source_dir_id, location

    async def async_delete_media(self, item: MediaSourceItem) -> None:
        """Delete media."""
        source_dir_id, location = self.async_parse_identifier(item)
        item_path = self.async_full_path(source_dir_id, location)

        def _do_delete() -> None:
            if not item_path.exists():
                raise FileNotFoundError("Path does not exist")

            if not item_path.is_file():
                raise PathNotSupportedError("Path is not a file")

            item_path.unlink()

        await self.hass.async_add_executor_job(_do_delete)

    async def async_upload_media(
        self, target_folder: MediaSourceItem, uploaded_file: UploadedFile
    ) -> str:
        """Upload media.

        Return value is the media source ID of the uploaded file.
        """
        source_dir_id, location = self.async_parse_identifier(target_folder)

        if not uploaded_file.content_type.startswith(("image/", "video/", "audio/")):
            LOGGER.error("Content type not allowed")
            raise vol.Invalid("Only images and video are allowed")

        try:
            raise_if_invalid_filename(uploaded_file.filename)
        except ValueError as err:
            raise InvalidFileNameError from err

        target_dir = self.async_full_path(source_dir_id, location)

        def _do_move() -> None:
            """Move file to target."""
            try:
                target_path = target_dir / uploaded_file.filename

                target_path.relative_to(target_dir)
                raise_if_invalid_path(str(target_path))

                target_dir.mkdir(parents=True, exist_ok=True)
            except ValueError as err:
                raise PathNotSupportedError("Invalid path") from err

            with target_path.open("wb") as target_fp:
                shutil.copyfileobj(uploaded_file.file, target_fp)

        await self.hass.async_add_executor_job(
            _do_move,
        )

        return f"{target_folder.media_source_id}/{uploaded_file.filename}"

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        source_dir_id, location = self.async_parse_identifier(item)
        path = self.async_full_path(source_dir_id, location)
        mime_type, _ = mimetypes.guess_type(str(path))
        assert isinstance(mime_type, str)
        return PlayMedia(f"{self.url_prefix}/{item.identifier}", mime_type, path=path)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return media."""
        if item.identifier:
            try:
                source_dir_id, location = self.async_parse_identifier(item)
            except Unresolvable as err:
                raise BrowseError(str(err)) from err

        else:
            source_dir_id, location = None, ""

        return await self.hass.async_add_executor_job(
            self._browse_media, source_dir_id, location
        )

    def _browse_media(
        self, source_dir_id: str | None, location: str
    ) -> BrowseMediaSource:
        """Browse media."""

        # If only one media dir is configured, use that as the local media root
        if source_dir_id is None and len(self.media_dirs) == 1:
            source_dir_id = list(self.media_dirs)[0]

        # Multiple folder, root is requested
        if source_dir_id is None:
            if location:
                raise BrowseError("Folder not found.")

            base = BrowseMediaSource(
                domain=self.domain,
                identifier="",
                media_class=MediaClass.DIRECTORY,
                media_content_type=None,
                title=self.name,
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.DIRECTORY,
            )

            base.children = [
                self._browse_media(source_dir_id, "")
                for source_dir_id in self.media_dirs
            ]

            return base

        full_path = Path(self.media_dirs[source_dir_id], location)

        if not full_path.exists():
            if location == "":
                raise BrowseError("Media directory does not exist.")
            raise BrowseError("Path does not exist.")

        if not full_path.is_dir():
            raise BrowseError("Path is not a directory.")

        result = self._build_item_response(source_dir_id, full_path)
        if not result:
            raise BrowseError("Unknown source directory.")
        return result

    def _build_item_response(
        self, source_dir_id: str, path: Path, is_child: bool = False
    ) -> BrowseMediaSource | None:
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

        media_class = MediaClass.DIRECTORY
        if mime_type:
            media_class = MEDIA_CLASS_MAP.get(
                mime_type.split("/")[0], MediaClass.DIRECTORY
            )

        media = BrowseMediaSource(
            domain=self.domain,
            identifier=f"{source_dir_id}/{path.relative_to(self.media_dirs[source_dir_id])}",
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
            if child_path.name[0] != ".":
                child = self._build_item_response(source_dir_id, child_path, True)
                if child:
                    media.children.append(child)

        # Sort children showing directories first, then by name
        media.children.sort(key=lambda child: (child.can_play, child.title))

        return media


class LocalMediaView(http.HomeAssistantView):
    """Local Media Finder View.

    Returns media files in config/media.
    """

    name = "media"

    def __init__(self, hass: HomeAssistant, source: LocalSource) -> None:
        """Initialize the media view."""
        self.hass = hass
        self.source = source
        self.name = source.url_prefix.strip("/").replace("/", ":")
        self.url = f"{source.url_prefix}/{{source_dir_id}}/{{location:.*}}"

    async def _validate_media_path(self, source_dir_id: str, location: str) -> Path:
        """Validate media path and return it if valid."""
        try:
            raise_if_invalid_path(location)
        except ValueError as err:
            raise web.HTTPBadRequest from err

        if source_dir_id not in self.source.media_dirs:
            raise web.HTTPNotFound

        media_path = self.source.async_full_path(source_dir_id, location)

        # Check that the file exists
        if not self.hass.async_add_executor_job(media_path.is_file):
            raise web.HTTPNotFound

        # Check that it's a media file
        mime_type, _ = mimetypes.guess_type(str(media_path))
        if not mime_type or mime_type.split("/")[0] not in MEDIA_MIME_TYPES:
            raise web.HTTPNotFound

        return media_path

    async def head(
        self, request: web.Request, source_dir_id: str, location: str
    ) -> None:
        """Handle a HEAD request.

        This is sent by some DLNA renderers, like Samsung ones, prior to sending
        the GET request.

        Check whether the location exists or not.
        """
        await self._validate_media_path(source_dir_id, location)

    async def get(
        self, request: web.Request, source_dir_id: str, location: str
    ) -> web.FileResponse:
        """Handle a GET request."""
        media_path = await self._validate_media_path(source_dir_id, location)
        return web.FileResponse(media_path)


class UploadMediaView(http.HomeAssistantView):
    """View to upload images."""

    url = "/api/media_source/local_source/upload"
    name = "api:media_source:local_source:upload"
    schema = vol.Schema(
        {
            "media_content_id": str,
            "file": FileField,
        }
    )

    @require_admin
    async def post(self, request: web.Request) -> web.Response:
        """Handle upload."""
        hass = request.app[http.KEY_HASS]

        # Increase max payload
        request._client_max_size = MAX_UPLOAD_SIZE  # noqa: SLF001

        try:
            data = self.schema(dict(await request.post()))
        except vol.Invalid as err:
            LOGGER.error("Received invalid upload data: %s", err)
            raise web.HTTPBadRequest from err

        try:
            target_folder = MediaSourceItem.from_uri(
                hass, data["media_content_id"], None
            )
        except ValueError as err:
            LOGGER.error("Received invalid upload data: %s", err)
            raise web.HTTPBadRequest from err

        if target_folder.domain != DOMAIN:
            raise web.HTTPBadRequest

        source = cast(LocalSource, hass.data[MEDIA_SOURCE_DATA][target_folder.domain])
        try:
            uploaded_media_source_id = await source.async_upload_media(
                target_folder, data["file"]
            )
        except Unresolvable as err:
            LOGGER.error("Invalid local source ID: %s", data["media_content_id"])
            raise web.HTTPBadRequest from err
        except InvalidFileNameError as err:
            LOGGER.error("Invalid filename uploaded: %s", data["file"].filename)
            raise web.HTTPBadRequest from err
        except PathNotSupportedError as err:
            LOGGER.error("Invalid path for upload: %s", data["media_content_id"])
            raise web.HTTPBadRequest from err
        except OSError as err:
            LOGGER.error("Error uploading file: %s", err)
            raise web.HTTPInternalServerError from err

        return self.json({"media_content_id": uploaded_media_source_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "media_source/local_source/remove",
        vol.Required("media_content_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_remove_media(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove media."""
    try:
        item = MediaSourceItem.from_uri(hass, msg["media_content_id"], None)
    except ValueError as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
        return

    if item.domain != DOMAIN:
        connection.send_error(
            msg["id"], websocket_api.ERR_INVALID_FORMAT, "Invalid media source domain"
        )
        return

    source = cast(LocalSource, hass.data[MEDIA_SOURCE_DATA][item.domain])

    try:
        await source.async_delete_media(item)
    except Unresolvable as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
    except FileNotFoundError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))
    except PathNotSupportedError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_SUPPORTED, str(err))
    except OSError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))
    else:
        connection.send_result(msg["id"])
