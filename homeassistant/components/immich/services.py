"""Services for the Immich integration."""

import logging
import os.path

from aioimmich.exceptions import ImmichError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .coordinator import ImmichDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONF_ALBUM_ID = "album_id"
CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_FILE = "file"

SERVICE_UPLOAD_FILE = "upload_file"
SERVICE_SCHEMA_UPLOAD_FILE = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): str,
        vol.Required(CONF_FILE): str,
        vol.Optional(CONF_ALBUM_ID): str,
    }
)


async def _async_upload_file(service_call: ServiceCall) -> None:
    """Call immich upload file service."""
    _LOGGER.debug(
        "Executing service %s with arguments %s",
        service_call.service,
        service_call.data,
    )
    hass = service_call.hass
    target_entry = hass.config_entries.async_get_entry(
        service_call.data[CONF_CONFIG_ENTRY_ID]
    )
    target_file = service_call.data[CONF_FILE]

    if not target_entry:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
            translation_placeholders={"service": service_call.service},
        )

    if target_entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
            translation_placeholders={"service": service_call.service},
        )

    if not os.path.isfile(target_file):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="file_not_found",
            translation_placeholders={
                "service": service_call.service,
                "file": target_file,
            },
        )

    coordinator: ImmichDataUpdateCoordinator = target_entry.runtime_data

    if target_album := service_call.data.get(CONF_ALBUM_ID):
        try:
            await coordinator.api.albums.async_get_album_info(target_album, True)
        except ImmichError as ex:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="album_not_found",
                translation_placeholders={
                    "service": service_call.service,
                    "album_id": target_album,
                    "error": str(ex),
                },
            ) from ex

    try:
        upload_result = await coordinator.api.assets.async_upload_asset(target_file)
        if target_album:
            await coordinator.api.albums.async_add_assets_to_album(
                target_album, [upload_result.asset_id]
            )
    except ImmichError as ex:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="upload_failed",
            translation_placeholders={
                "service": service_call.service,
                "file": target_file,
                "error": str(ex),
            },
        ) from ex


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for immich integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPLOAD_FILE,
        _async_upload_file,
        SERVICE_SCHEMA_UPLOAD_FILE,
    )
