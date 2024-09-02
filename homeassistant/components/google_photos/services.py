"""Google Photos services."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILENAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from . import api
from .const import DOMAIN, UPLOAD_SCOPE

type GooglePhotosConfigEntry = ConfigEntry[api.AsyncConfigEntryAuth]

__all__ = [
    "DOMAIN",
]

CONF_CONFIG_ENTRY_ID = "config_entry_id"

UPLOAD_SERVICE = "upload"
UPLOAD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(CONF_FILENAME): vol.All(cv.ensure_list, [cv.string]),
    }
)


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

        client_api = config_entry.runtime_data
        upload_tasks = []
        file_results = await hass.async_add_executor_job(
            _read_file_contents, hass, call.data[CONF_FILENAME]
        )
        for mime_type, content in file_results:
            upload_tasks.append(client_api.upload_content(content, mime_type))
        upload_tokens = await asyncio.gather(*upload_tasks)
        media_ids = await client_api.create_media_items(upload_tokens)
        if call.return_response:
            return {
                "media_items": [{"media_item_id": media_id for media_id in media_ids}]
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
