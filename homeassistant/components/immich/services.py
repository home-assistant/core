"""Services for the Immich integration."""

import logging

from aioimmich.exceptions import ImmichError
import voluptuous as vol

from homeassistant.components.media_source import async_resolve_media
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.selector import MediaSelector

from .const import DOMAIN
from .coordinator import ImmichConfigEntry

_LOGGER = logging.getLogger(__name__)

CONF_ALBUM_ID = "album_id"
CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_FILE = "file"

SERVICE_UPLOAD_FILE = "upload_file"
SERVICE_SCHEMA_UPLOAD_FILE = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): str,
        vol.Required(CONF_FILE): MediaSelector({"accept": ["image/*", "video/*"]}),
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
    target_entry: ImmichConfigEntry | None = hass.config_entries.async_get_entry(
        service_call.data[CONF_CONFIG_ENTRY_ID]
    )
    source_media_id = service_call.data[CONF_FILE]["media_content_id"]

    if not target_entry:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
        )

    if target_entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
        )

    media = await async_resolve_media(hass, source_media_id, None)
    if media.path is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="only_local_media_supported"
        )

    coordinator = target_entry.runtime_data

    if target_album := service_call.data.get(CONF_ALBUM_ID):
        try:
            await coordinator.api.albums.async_get_album_info(target_album, True)
        except ImmichError as ex:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="album_not_found",
                translation_placeholders={"album_id": target_album, "error": str(ex)},
            ) from ex

    try:
        upload_result = await coordinator.api.assets.async_upload_asset(str(media.path))
        if target_album:
            await coordinator.api.albums.async_add_assets_to_album(
                target_album, [upload_result.asset_id]
            )
    except ImmichError as ex:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="upload_failed",
            translation_placeholders={"file": str(media.path), "error": str(ex)},
        ) from ex


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for immich integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPLOAD_FILE,
        _async_upload_file,
        SERVICE_SCHEMA_UPLOAD_FILE,
    )
