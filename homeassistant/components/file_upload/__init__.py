"""The File Upload integration."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import raise_if_invalid_filename
from homeassistant.util.ulid import ulid_hex

DOMAIN = "file_upload"

# If increased, change upload view to streaming
# https://docs.aiohttp.org/en/stable/web_quickstart.html#file-uploads
MAX_SIZE = 1024 * 1024 * 10
TEMP_DIR_NAME = f"home-assistant-{DOMAIN}"


@contextmanager
def process_uploaded_file(hass: HomeAssistant, file_id: str) -> Iterator[Path]:
    """Get an uploaded file.

    File is removed at the end of the context.
    """
    if DOMAIN not in hass.data:
        raise ValueError("File does not exist")

    file_upload_data: FileUploadData = hass.data[DOMAIN]

    if not file_upload_data.has_file(file_id):
        raise ValueError("File does not exist")

    try:
        yield file_upload_data.file_path(file_id)
    finally:
        file_upload_data.files.pop(file_id)
        shutil.rmtree(file_upload_data.file_dir(file_id))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up File Upload."""
    hass.http.register_view(FileUploadView)
    return True


@dataclass(frozen=True)
class FileUploadData:
    """File upload data."""

    temp_dir: Path
    files: dict[str, str]

    @classmethod
    async def create(cls, hass: HomeAssistant) -> FileUploadData:
        """Initialize the file upload data."""

        def _create_temp_dir() -> Path:
            """Create temporary directory."""
            temp_dir = Path(tempfile.gettempdir()) / TEMP_DIR_NAME

            # If it exists, it's an old one and Home Assistant didn't shut down correctly.
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

            temp_dir.mkdir(0o700)
            return temp_dir

        temp_dir = await hass.async_add_executor_job(_create_temp_dir)

        def cleanup_unused_files(ev: Event) -> None:
            """Clean up unused files."""
            shutil.rmtree(temp_dir)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_unused_files)

        return cls(temp_dir, {})

    def has_file(self, file_id: str) -> bool:
        """Return if file exists."""
        return file_id in self.files

    def file_dir(self, file_id: str) -> Path:
        """Return the file directory."""
        return self.temp_dir / file_id

    def file_path(self, file_id: str) -> Path:
        """Return the file path."""
        return self.file_dir(file_id) / self.files[file_id]


class FileUploadView(HomeAssistantView):
    """HTTP View to upload files."""

    url = "/api/file_upload"
    name = "api:file_upload"

    _upload_lock: asyncio.Lock | None = None

    @callback
    def _get_upload_lock(self) -> asyncio.Lock:
        """Get upload lock."""
        if self._upload_lock is None:
            self._upload_lock = asyncio.Lock()

        return self._upload_lock

    async def post(self, request: web.Request) -> web.Response:
        """Upload a file."""
        async with self._get_upload_lock():
            return await self._upload_file(request)

    async def _upload_file(self, request: web.Request) -> web.Response:
        """Handle uploaded file."""
        # Increase max payload
        request._client_max_size = MAX_SIZE  # pylint: disable=protected-access

        data = await request.post()
        file_field = data.get("file")

        if not isinstance(file_field, web.FileField):
            raise vol.Invalid("Expected a file")

        try:
            raise_if_invalid_filename(file_field.filename)
        except ValueError as err:
            raise web.HTTPBadRequest from err

        hass: HomeAssistant = request.app["hass"]
        file_id = ulid_hex()

        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = await FileUploadData.create(hass)

        file_upload_data: FileUploadData = hass.data[DOMAIN]
        file_dir = file_upload_data.file_dir(file_id)

        def _sync_work() -> None:
            file_dir.mkdir()

            # MyPy forgets about the isinstance check because we're in a function scope
            assert isinstance(file_field, web.FileField)

            with (file_dir / file_field.filename).open("wb") as target_fileobj:
                shutil.copyfileobj(file_field.file, target_fileobj)

        await hass.async_add_executor_job(_sync_work)

        file_upload_data.files[file_id] = file_field.filename

        return self.json({"file_id": file_id})

    @RequestDataValidator({vol.Required("file_id"): str})
    async def delete(self, request: web.Request, data: dict[str, str]) -> web.Response:
        """Delete a file."""
        hass: HomeAssistant = request.app["hass"]

        if DOMAIN not in hass.data:
            raise web.HTTPNotFound()

        file_id = data["file_id"]
        file_upload_data: FileUploadData = hass.data[DOMAIN]

        if file_upload_data.files.pop(file_id, None) is None:
            raise web.HTTPNotFound()

        await hass.async_add_executor_job(
            lambda: shutil.rmtree(file_upload_data.file_dir(file_id))
        )

        return self.json_message("File deleted")
