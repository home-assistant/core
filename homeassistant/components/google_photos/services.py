"""Google Photos services."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path

from google_photos_library_api.exceptions import GooglePhotosApiError
from google_photos_library_api.model import NewMediaItem, SimpleMediaItem
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

from .const import DOMAIN, UPLOAD_SCOPE
from .coordinator import GooglePhotosConfigEntry

CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_ALBUM = "album"

UPLOAD_SERVICE = "upload"
UPLOAD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(CONF_FILENAME): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(CONF_ALBUM): cv.string,
    }
)
CONTENT_SIZE_LIMIT = 20 * 1024 * 1024


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
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type is None or not (mime_type.startswith(("image", "video"))):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="filename_is_not_image",
                translation_placeholders={"filename": filename},
            )
        results.append((mime_type, filename_path.read_bytes()))
    return results


def async_register_services(hass: HomeAssistant) -> None:
    """Register Google Photos services."""

    async def async_handle_upload(call: ServiceCall) -> ServiceResponse:
        """Generate content from text and optionally images."""
        config_entry: GooglePhotosConfigEntry | None = (
            hass.config_entries.async_get_entry(call.data[CONF_CONFIG_ENTRY_ID])
        )
        if not config_entry:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="integration_not_found",
                translation_placeholders={"target": DOMAIN},
            )
        scopes = config_entry.data["token"]["scope"].split(" ")
        if UPLOAD_SCOPE not in scopes:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="missing_upload_permission",
                translation_placeholders={"target": DOMAIN},
            )
        coordinator = config_entry.runtime_data
        client_api = coordinator.client
        upload_tasks = []
        file_results = await hass.async_add_executor_job(
            _read_file_contents, hass, call.data[CONF_FILENAME]
        )

        album = call.data[CONF_ALBUM]
        try:
            album_id = await coordinator.get_or_create_album(album)
        except GooglePhotosApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="create_album_error",
                translation_placeholders={"message": str(err)},
            ) from err

        for mime_type, content in file_results:
            upload_tasks.append(client_api.upload_content(content, mime_type))
        try:
            upload_results = await asyncio.gather(*upload_tasks)
        except GooglePhotosApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="upload_error",
                translation_placeholders={"message": str(err)},
            ) from err
        try:
            upload_result = await client_api.create_media_items(
                [
                    NewMediaItem(
                        SimpleMediaItem(upload_token=upload_result.upload_token)
                    )
                    for upload_result in upload_results
                ],
                album_id=album_id,
            )
        except GooglePhotosApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"message": str(err)},
            ) from err
        if call.return_response:
            return {
                "media_items": [
                    {"media_item_id": item_result.media_item.id}
                    for item_result in upload_result.new_media_item_results
                    if item_result.media_item and item_result.media_item.id
                ],
                "album_id": album_id,
            }
        return None

    if not hass.services.has_service(DOMAIN, UPLOAD_SERVICE):
        hass.services.async_register(
            DOMAIN,
            UPLOAD_SERVICE,
            async_handle_upload,
            schema=UPLOAD_SERVICE_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
