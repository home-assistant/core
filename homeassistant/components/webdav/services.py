"""WebDAV services."""

from collections.abc import AsyncIterator
import glob
from pathlib import Path, PurePosixPath

from aiohttp import ClientTimeout
from aiowebdav2.exceptions import UnauthorizedError, WebDavError
import probatio

from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_FILENAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.util.async_ import gather_with_limited_concurrency

from .const import DOMAIN
from .helpers import WebDavConfigEntry

CONF_DESTINATION_FOLDER = "destination_folder"

UPLOAD_SERVICE = "upload"
UPLOAD_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Required(CONF_FILENAME): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Required(CONF_DESTINATION_FOLDER): cv.string,
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


def _resolve_files(
    hass: HomeAssistant, filenames: list[str]
) -> list[tuple[Path, str, int]]:
    """Return the local path, destination-relative path and size of each file."""
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
    return [
        (Path(full_path), relative_path, Path(full_path).stat().st_size)
        for full_path, relative_path in files
    ]


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


async def _iter_file(hass: HomeAssistant, path: Path) -> AsyncIterator[bytes]:
    """Read a local file in chunks without blocking the event loop."""
    file = await hass.async_add_executor_job(path.open, "rb")
    try:
        while chunk := await hass.async_add_executor_job(file.read, CHUNK_SIZE):
            yield chunk
    finally:
        await hass.async_add_executor_job(file.close)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register WebDAV services."""

    async def async_handle_upload(call: ServiceCall) -> ServiceResponse:
        """Upload one or more files to the WebDAV server."""
        config_entry: WebDavConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
        )
        client = config_entry.runtime_data
        destination_folder = call.data[CONF_DESTINATION_FOLDER]

        files = await hass.async_add_executor_job(
            _resolve_files, hass, call.data[CONF_FILENAME]
        )
        uploads = [
            (local_path, _remote_path(destination_folder, relative_path), size)
            for local_path, relative_path, size in files
        ]
        folders = sorted(
            {
                str(remote.parent)
                for _, remote, _ in uploads
                if remote.parent != PurePosixPath("/")
            }
        )

        try:
            for folder in folders:
                await client.mkdir(folder, parents=True, exist_ok=True)
        except UnauthorizedError as err:
            config_entry.async_start_reauth(hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_username_password",
            ) from err
        except (WebDavError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="create_folder_error",
                translation_placeholders={"message": str(err)},
            ) from err

        try:
            await gather_with_limited_concurrency(
                UPLOAD_CONCURRENCY,
                *(
                    client.write(
                        str(remote),
                        _iter_file(hass, local_path),
                        content_length=size,
                        timeout=UPLOAD_TIMEOUT,
                    )
                    for local_path, remote, size in uploads
                ),
            )
        except UnauthorizedError as err:
            config_entry.async_start_reauth(hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_username_password",
            ) from err
        except (WebDavError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="upload_error",
                translation_placeholders={"message": str(err)},
            ) from err

        if call.return_response:
            return {"files": [{"path": str(remote)} for _, remote, _ in uploads]}
        return None

    hass.services.async_register(
        DOMAIN,
        UPLOAD_SERVICE,
        async_handle_upload,
        schema=UPLOAD_SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
        description_placeholders={"example_image_path": "/config/www/image.jpg"},
    )
