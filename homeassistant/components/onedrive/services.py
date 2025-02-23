"""OneDrive services."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import cast

from onedrive_personal_sdk.exceptions import OneDriveException
import voluptuous as vol

from homeassistant.const import CONF_FILENAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import OneDriveConfigEntry

CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_DESTINATION_FOLDER = "destination_folder"

UPLOAD_SERVICE = "upload"
UPLOAD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(CONF_FILENAME): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(CONF_DESTINATION_FOLDER): cv.string,
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


def async_register_services(hass: HomeAssistant) -> None:
    """Register OneDrive services."""

    async def async_handle_upload(call: ServiceCall) -> ServiceResponse:
        """Generate content from text and optionally images."""
        config_entry: OneDriveConfigEntry | None = hass.config_entries.async_get_entry(
            call.data[CONF_CONFIG_ENTRY_ID]
        )
        if not config_entry:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="integration_not_found",
                translation_placeholders={"target": DOMAIN},
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

    if not hass.services.has_service(DOMAIN, UPLOAD_SERVICE):
        hass.services.async_register(
            DOMAIN,
            UPLOAD_SERVICE,
            async_handle_upload,
            schema=UPLOAD_SERVICE_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
