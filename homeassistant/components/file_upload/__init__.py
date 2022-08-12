"""The File Upload integration."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
from uuid import UUID

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
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

    # Validate file_id
    UUID(file_id)

    temp_dir: Path = hass.data[DOMAIN]
    source_dir = temp_dir / file_id
    source_file = list(source_dir.iterdir())[0]

    try:
        yield source_file
    finally:
        shutil.rmtree(source_dir)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up File Upload."""
    hass.http.register_view(FileUploadView)
    return True


async def _get_temp_dir(hass: HomeAssistant) -> Path:
    """Return the temporary directory."""

    def _create_temp_dir() -> Path:
        """Create temporary directory."""
        temp_dir = Path(tempfile.gettempdir()) / TEMP_DIR_NAME
        # If it exists, it's an old one and Home Assistant didn't shut down correctly.
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        return temp_dir

    temp_dir = Path(await hass.async_add_executor_job(_create_temp_dir))

    def cleanup_unused_files(ev: Event) -> None:
        """Clean up unused files."""
        shutil.rmtree(temp_dir)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_unused_files)

    return temp_dir


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

        hass: HomeAssistant = request.app["hass"]
        file_id = ulid_hex()

        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = await _get_temp_dir(hass)

        temp_dir: Path = hass.data[DOMAIN]

        target_dir = temp_dir / file_id
        target_file = target_dir / file_field.filename

        def _sync_work() -> None:
            target_dir.mkdir()

            with target_file.open("wb") as target_fileobj:
                # MyPy forgets about the isinstance check because we're in a function scope
                shutil.copyfileobj(file_field.file, target_fileobj)  # type: ignore[union-attr]

        await hass.async_add_executor_job(_sync_work)

        return self.json({"file_id": file_id})

    @RequestDataValidator({vol.Required("file_id"): str})
    async def delete(self, request: web.Request, data: dict[str, str]) -> web.Response:
        """Delete a file."""
        hass: HomeAssistant = request.app["hass"]

        file_id = data["file_id"]

        # Validate file_id
        try:
            UUID(file_id)
        except ValueError as err:
            raise web.HTTPBadRequest() from err

        if DOMAIN in hass.data:
            temp_dir: Path = hass.data[DOMAIN]
        else:
            temp_dir = await _get_temp_dir(hass)

        source_dir = temp_dir / file_id

        try:
            await hass.async_add_executor_job(lambda: shutil.rmtree(source_dir))
        except FileNotFoundError as err:
            raise web.HTTPNotFound() from err

        return self.json_message("File deleted")
