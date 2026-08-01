"""OneDrive services."""

import asyncio
from dataclasses import asdict
import glob
from pathlib import Path, PurePosixPath
from typing import cast

from onedrive_personal_sdk.exceptions import OneDriveException
import voluptuous as vol

from homeassistant.const import CONF_FILENAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service

from .const import CONF_DELETE_PERMANENTLY, DOMAIN
from .coordinator import OneDriveConfigEntry

CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_DESTINATION_FOLDER = "destination_folder"
CONF_DESTINATION_PATH = "destination_path"

UPLOAD_SERVICE = "upload"
UPLOAD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(CONF_FILENAME): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(CONF_DESTINATION_FOLDER): cv.string,
    }
)

DELETE_SERVICE = "delete"
DELETE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(CONF_DESTINATION_PATH): vol.All(
            cv.ensure_list, vol.Length(min=1), [cv.string]
        ),
    }
)

CONTENT_SIZE_LIMIT = 250 * 1024 * 1024


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
            raise HomeAssistantError(
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
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_files_match_pattern",
            translation_placeholders={
                "patterns": ", ".join(f"`{p}`" for p in no_matches)
            },
        )
    return list(expanded.items())


def _destination_parts(relative_path: str) -> tuple[str, str]:
    """Split a relative path into its subfolder path and file name."""
    path = PurePosixPath(relative_path)
    parent = str(path.parent)
    return ("" if parent == "." else parent, path.name)


def _read_file_contents(
    hass: HomeAssistant, filenames: list[str]
) -> list[tuple[str, bytes]]:
    """Return the destination-relative path and file contents for each file."""
    files = _expand_filenames(hass, filenames)
    missing: list[str] = []
    for full_path, _ in files:
        if not hass.config.is_allowed_path(full_path):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_access_to_path",
                translation_placeholders={"filename": full_path},
            )
        if not Path(full_path).exists():
            missing.append(full_path)
    if missing:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="filenames_do_not_exist",
            translation_placeholders={
                "filenames": ", ".join(f"`{f}`" for f in missing)
            },
        )
    results = []
    for full_path, relative_path in files:
        path = Path(full_path)
        file_size = path.stat().st_size
        if file_size > CONTENT_SIZE_LIMIT:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="file_too_large",
                translation_placeholders={
                    "filename": full_path,
                    "size": str(file_size),
                    "limit": str(CONTENT_SIZE_LIMIT),
                },
            )
        results.append((relative_path, path.read_bytes()))
    return results


def _raise_invalid_destination_path(destination_path: str) -> None:
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="invalid_destination_path",
        translation_placeholders={"destination_path": destination_path},
    )


def _validate_destination_path(destination_path: str) -> str:
    """Validate and normalize a remote destination path.

    Returns the normalized path or raises HomeAssistantError.
    """
    normalized = destination_path.strip("/")
    if not normalized:
        _raise_invalid_destination_path(destination_path)
    parts = PurePosixPath(normalized).parts
    for part in parts:
        if part == ".." or ":" in part:
            _raise_invalid_destination_path(destination_path)
    return str(PurePosixPath(normalized))


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register OneDrive services."""

    async def async_handle_upload(call: ServiceCall) -> ServiceResponse:
        """Generate content from text and optionally images."""
        config_entry: OneDriveConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data[CONF_CONFIG_ENTRY_ID]
        )
        client = config_entry.runtime_data.client
        file_results = await hass.async_add_executor_job(
            _read_file_contents, hass, call.data[CONF_FILENAME]
        )

        # make sure the destination folders exist, preserving subfolder structure
        folder_ids: dict[str, str] = {}
        try:
            base_folder_id = (await client.get_approot()).id
            for folder in (
                cast(str, call.data[CONF_DESTINATION_FOLDER]).strip("/").split("/")
            ):
                base_folder_id = (await client.create_folder(base_folder_id, folder)).id
            folder_ids[""] = base_folder_id

            for relative_path, _ in file_results:
                sub_folder, _ = _destination_parts(relative_path)
                if sub_folder in folder_ids:
                    continue
                parent_id = base_folder_id
                accumulated = ""
                for part in PurePosixPath(sub_folder).parts:
                    accumulated = f"{accumulated}/{part}" if accumulated else part
                    if accumulated not in folder_ids:
                        folder_ids[accumulated] = (
                            await client.create_folder(parent_id, part)
                        ).id
                    parent_id = folder_ids[accumulated]
        except OneDriveException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="create_folder_error",
                translation_placeholders={"message": str(err)},
            ) from err

        upload_tasks = []
        for relative_path, content in file_results:
            sub_folder, name = _destination_parts(relative_path)
            upload_tasks.append(
                client.upload_file(folder_ids[sub_folder], name, content)
            )
        try:
            upload_results = await asyncio.gather(*upload_tasks)
        except OneDriveException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="upload_error",
                translation_placeholders={"message": str(err)},
            ) from err

        if call.return_response:
            return {"files": [asdict(item_result) for item_result in upload_results]}
        return None

    async def async_handle_delete(call: ServiceCall) -> None:
        """Delete one or more files from OneDrive."""
        config_entry: OneDriveConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data[CONF_CONFIG_ENTRY_ID]
        )
        client = config_entry.runtime_data.client
        delete_permanently = config_entry.options.get(CONF_DELETE_PERMANENTLY, False)
        file_paths = [
            _validate_destination_path(p)
            for p in cast(list[str], call.data[CONF_DESTINATION_PATH])
        ]

        try:
            approot_id = (await client.get_approot()).id
        except OneDriveException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err

        results = await asyncio.gather(
            *[
                client.delete_drive_item(
                    f"{approot_id}:/{file_path}:", delete_permanently
                )
                for file_path in file_paths
            ],
            return_exceptions=True,
        )
        failures: list[tuple[str, OneDriveException]] = []
        for file_path, result in zip(file_paths, results, strict=True):
            if isinstance(result, OneDriveException):
                failures.append((file_path, result))
        if failures:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="delete_error",
                translation_placeholders={
                    "paths": ", ".join(f"`{path}`" for path, _ in failures)
                },
            ) from ExceptionGroup(
                "OneDrive delete errors", [err for _, err in failures]
            )

    hass.services.async_register(
        DOMAIN,
        UPLOAD_SERVICE,
        async_handle_upload,
        schema=UPLOAD_SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
        description_placeholders={"example_image_path": "/config/www/image.jpg"},
    )

    hass.services.async_register(
        DOMAIN,
        DELETE_SERVICE,
        async_handle_delete,
        schema=DELETE_SERVICE_SCHEMA,
    )
