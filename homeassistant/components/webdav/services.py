"""WebDAV services."""

import asyncio
from collections import Counter
from collections.abc import AsyncIterator
import glob
import os
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from aiohttp import ClientTimeout
from aiowebdav2.client import Client
from aiowebdav2.exceptions import UnauthorizedError, WebDavError
import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.os_error import os_read_error

from .const import DOMAIN, WebDavService, WebDavServiceArgument
from .helpers import WebDavConfigEntry

UPLOAD_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Required(WebDavServiceArgument.FILENAME): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Required(WebDavServiceArgument.DESTINATION_FOLDER): cv.string,
    }
)

UPLOAD_CONCURRENCY = 4
UPLOAD_TIMEOUT = ClientTimeout(connect=10, total=43200)
CHUNK_SIZE = 1024 * 1024


def _split_glob_pattern(pattern: str) -> tuple[str, str]:
    """Split a glob pattern into its non-magic base directory and remaining pattern."""
    parts = Path(pattern).parts
    base_parts: list[str] = []
    for part in parts:
        if glob.has_magic(part):
            break
        base_parts.append(part)
    base = str(Path(*base_parts)) if base_parts else "."
    relative_pattern = str(Path(*parts[len(base_parts) :]))
    return base, relative_pattern


def _expand_filenames(
    hass: HomeAssistant, filenames: list[str]
) -> list[tuple[str, str]]:
    """Expand wildcard patterns, preserving subfolder structure."""
    expanded: dict[str, str] = {}
    no_matches: list[str] = []
    for filename in filenames:
        if not glob.has_magic(filename) or Path(filename).is_file():
            expanded.setdefault(filename, Path(filename).name)
            continue
        base, relative_pattern = _split_glob_pattern(filename)

        if not hass.config.is_allowed_path(base):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_access_to_path",
                translation_placeholders={"filename": base},
            )
        matches = sorted(
            match
            for match in glob.glob(relative_pattern, root_dir=base, recursive=True)
            if (Path(base) / match).is_file()
        )
        if not matches:
            no_matches.append(filename)
            continue
        for match in matches:
            full_path = str(Path(base) / match)
            relative_path = str(PurePosixPath(*Path(match).parts))
            expanded.setdefault(full_path, relative_path)
    if no_matches:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_files_match_pattern",
            translation_placeholders={
                "patterns": ", ".join(f"`{p}`" for p in no_matches)
            },
        )
    return list(expanded.items())


def _resolve_files(hass: HomeAssistant, filenames: list[str]) -> list[tuple[Path, str]]:
    """Return the local path and destination-relative path of each file."""
    files = _expand_filenames(hass, filenames)
    missing: list[str] = []
    for full_path, _ in files:
        if not hass.config.is_allowed_path(full_path):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_access_to_path",
                translation_placeholders={"filename": full_path},
            )
        if not Path(full_path).is_file():
            missing.append(full_path)
    if missing:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="filenames_do_not_exist",
            translation_placeholders={
                "filenames": ", ".join(f"`{f}`" for f in missing)
            },
        )
    return [(Path(full_path), relative_path) for full_path, relative_path in files]


def _remote_path(destination_folder: str, relative_path: str) -> PurePosixPath:
    """Build the absolute remote path, rejecting traversal outside the root."""
    path = PurePosixPath("/", destination_folder.strip("/"), relative_path)
    if ".." in path.parts:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_destination_path",
            translation_placeholders={"destination_path": str(path)},
        )
    return path


def _open_file(path: Path) -> tuple[BinaryIO, int]:
    """Open a local file and return it with the size of the opened file."""
    try:
        file = path.open("rb")
    except OSError as err:
        raise os_read_error(err, str(path)) from err
    return file, os.fstat(file.fileno()).st_size


async def _iter_file(
    hass: HomeAssistant, file: BinaryIO, size: int
) -> AsyncIterator[bytes]:
    """Read up to size bytes in chunks without blocking the event loop."""
    remaining = size
    while remaining and (
        chunk := await hass.async_add_executor_job(
            file.read, min(CHUNK_SIZE, remaining)
        )
    ):
        remaining -= len(chunk)
        yield chunk


async def _upload_file(
    hass: HomeAssistant,
    client: Client,
    semaphore: asyncio.Semaphore,
    local_path: Path,
    remote: PurePosixPath,
) -> None:
    """Upload one local file to the WebDAV server."""
    async with semaphore:
        file, size = await hass.async_add_executor_job(_open_file, local_path)
        try:
            # The size is taken from the opened file so Content-Length matches the body
            await client.write(
                str(remote),
                _iter_file(hass, file, size),
                content_length=size,
                timeout=UPLOAD_TIMEOUT,
            )
        finally:
            await hass.async_add_executor_job(file.close)


def _webdav_error(
    hass: HomeAssistant,
    config_entry: WebDavConfigEntry,
    err: WebDavError | TimeoutError,
    translation_key: str,
) -> HomeAssistantError:
    """Return a translated error for a WebDAV server error."""
    if isinstance(err, UnauthorizedError):
        config_entry.async_start_reauth(hass)
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_username_password",
        )
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=translation_key,
        translation_placeholders={"message": str(err)},
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register WebDAV services."""

    async def async_handle_upload(call: ServiceCall) -> ServiceResponse:
        """Upload one or more files to the WebDAV server."""
        config_entry: WebDavConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
        )
        client = config_entry.runtime_data
        destination_folder = call.data[WebDavServiceArgument.DESTINATION_FOLDER]

        files = await hass.async_add_executor_job(
            _resolve_files, hass, call.data[WebDavServiceArgument.FILENAME]
        )
        uploads = [
            (local_path, _remote_path(destination_folder, relative_path))
            for local_path, relative_path in files
        ]
        remote_counts = Counter(str(remote) for _, remote in uploads)
        if duplicates := sorted(
            path for path, count in remote_counts.items() if count > 1
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="duplicate_destination_path",
                translation_placeholders={
                    "paths": ", ".join(f"`{path}`" for path in duplicates)
                },
            )
        folders = sorted(
            {
                str(remote.parent)
                for _, remote in uploads
                if remote.parent != PurePosixPath("/")
            }
        )

        try:
            for folder in folders:
                await client.mkdir(folder, parents=True, exist_ok=True)
        except (WebDavError, TimeoutError) as err:
            raise _webdav_error(hass, config_entry, err, "create_folder_error") from err

        semaphore = asyncio.Semaphore(UPLOAD_CONCURRENCY)
        try:
            async with asyncio.TaskGroup() as group:
                for local_path, remote in uploads:
                    group.create_task(
                        _upload_file(hass, client, semaphore, local_path, remote)
                    )
        except ExceptionGroup as err_group:
            error = next(
                (e for e in err_group.exceptions if isinstance(e, UnauthorizedError)),
                err_group.exceptions[0],
            )
            if isinstance(error, HomeAssistantError):
                raise error from error.__cause__
            if isinstance(error, (WebDavError, TimeoutError)):
                raise _webdav_error(
                    hass, config_entry, error, "upload_error"
                ) from error
            raise

        if call.return_response:
            return {"files": [{"path": str(remote)} for _, remote in uploads]}
        return None

    service.async_register_admin_service(
        hass,
        DOMAIN,
        WebDavService.UPLOAD,
        async_handle_upload,
        schema=UPLOAD_SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
        description_placeholders={"example_image_path": "/config/www/image.jpg"},
    )
