"""OneDrive services."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict
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
        vol.Optional(CONF_FILENAME): vol.All(cv.ensure_list, [cv.string]),
    }
)

CONTENT_SIZE_LIMIT = 250 * 1024 * 1024


def _read_file_contents(
    hass: HomeAssistant, filenames: list[str]
) -> list[tuple[str, bytes]]:
    """Return the mime types and file contents for each file."""
    results = []
    for filename in filenames:
        if not hass.config.is_allowed_path(filename):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_access_to_path",
                translation_placeholders={"filename": filename},
            )
        filename_path = Path(filename)
        if not filename_path.exists():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="filename_does_not_exist",
                translation_placeholders={"filename": filename},
            )
        if filename_path.stat().st_size > CONTENT_SIZE_LIMIT:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="file_too_large",
                translation_placeholders={
                    "filename": filename,
                    "size": str(filename_path.stat().st_size),
                    "limit": str(CONTENT_SIZE_LIMIT),
                },
            )
        results.append((filename_path.name, filename_path.read_bytes()))
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


def _check_local_files_allowed(
    is_allowed_path: Callable[[str], bool], filenames: list[str]
) -> None:
    """Raise HomeAssistantError if any filename is not in the allowlist."""
    for filename in filenames:
        if not is_allowed_path(filename):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_delete_access_to_path",
                translation_placeholders={"filename": filename},
            )


def _check_local_files_exist(filenames: list[str]) -> None:
    """Raise HomeAssistantError if any filename does not exist."""
    for filename in filenames:
        if not Path(filename).exists():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="filename_does_not_exist",
                translation_placeholders={"filename": filename},
            )


def _delete_local_files(filenames: list[str]) -> None:
    """Delete local files, ignoring files that no longer exist."""
    for filename in filenames:
        try:
            Path(filename).unlink()
        except FileNotFoundError:
            pass
        except OSError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="delete_local_file_error",
                translation_placeholders={"filename": filename, "message": str(err)},
            ) from err


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register OneDrive services."""

    async def async_handle_upload(call: ServiceCall) -> ServiceResponse:
        """Generate content from text and optionally images."""
        config_entry: OneDriveConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data[CONF_CONFIG_ENTRY_ID]
        )
        client = config_entry.runtime_data.client
        upload_tasks = []
        file_results = await hass.async_add_executor_job(
            _read_file_contents, hass, call.data[CONF_FILENAME]
        )

        # make sure the destination folder exists
        try:
            folder_id = (await client.get_approot()).id
            for folder in (
                cast(str, call.data[CONF_DESTINATION_FOLDER]).strip("/").split("/")
            ):
                folder_id = (await client.create_folder(folder_id, folder)).id
        except OneDriveException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="create_folder_error",
                translation_placeholders={"message": str(err)},
            ) from err

        upload_tasks = [
            client.upload_file(folder_id, file_name, content)
            for file_name, content in file_results
        ]
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
        """Delete a file from OneDrive and optionally from the local filesystem."""
        config_entry: OneDriveConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data[CONF_CONFIG_ENTRY_ID]
        )
        client = config_entry.runtime_data.client
        delete_permanently = config_entry.options.get(CONF_DELETE_PERMANENTLY, False)
        file_paths = [
            _validate_destination_path(p)
            for p in cast(list[str], call.data[CONF_DESTINATION_PATH])
        ]
        local_filenames = cast(list[str], call.data.get(CONF_FILENAME, []))

        # allowlist check runs on the event loop (thread-safe); existence check
        # is offloaded to an executor because it performs blocking I/O
        if local_filenames:
            _check_local_files_allowed(hass.config.is_allowed_path, local_filenames)
            await hass.async_add_executor_job(_check_local_files_exist, local_filenames)

        approot_id = (await client.get_approot()).id
        results = await asyncio.gather(
            *[
                client.delete_drive_item(
                    f"{approot_id}:/{file_path}:", delete_permanently
                )
                for file_path in file_paths
            ],
            return_exceptions=True,
        )
        errors = [r for r in results if isinstance(r, OneDriveException)]
        if errors:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="delete_error",
                translation_placeholders={"message": "; ".join(str(e) for e in errors)},
            ) from errors[0]

        if local_filenames:
            await hass.async_add_executor_job(_delete_local_files, local_filenames)

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
