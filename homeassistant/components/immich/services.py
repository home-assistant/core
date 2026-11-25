"""Services for the Immich integration."""

from enum import StrEnum
import logging

from aioimmich.exceptions import ImmichError
import probatio

from homeassistant.components.media_source import async_resolve_media
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import service
from homeassistant.helpers.os_error import os_read_error
from homeassistant.helpers.selector import MediaSelector

from .const import DOMAIN
from .coordinator import ImmichConfigEntry

_LOGGER = logging.getLogger(__name__)


class ImmichService(StrEnum):
    """Store keys for Immich services."""

    UPLOAD_FILE = "upload_file"


class ImmichServiceArgument(StrEnum):
    """Store keys for Immich service arguments."""

    FILE = "file"
    ALBUM_ID = "album_id"


SERVICE_SCHEMA_UPLOAD_FILE = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): str,
        probatio.Required(ImmichServiceArgument.FILE): MediaSelector(
            {"accept": ["image/*", "video/*"]}
        ),
        probatio.Optional(ImmichServiceArgument.ALBUM_ID): str,
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
    target_entry: ImmichConfigEntry = service.async_get_config_entry(
        hass, DOMAIN, service_call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )
    source_media_id = service_call.data[ImmichServiceArgument.FILE]["media_content_id"]

    media = await async_resolve_media(hass, source_media_id, None)
    if media.path is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="only_local_media_supported"
        )

    coordinator = target_entry.runtime_data

    if target_album := service_call.data.get(ImmichServiceArgument.ALBUM_ID):
        try:
            await coordinator.api.albums.async_get_album_info(target_album)
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
    except OSError as err:
        raise os_read_error(err, str(media.path)) from err
    except ImmichError as ex:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="upload_failed",
            translation_placeholders={"file": str(media.path), "error": str(ex)},
        ) from ex


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for immich integration."""

    hass.services.async_register(
        DOMAIN,
        ImmichService.UPLOAD_FILE,
        _async_upload_file,
        SERVICE_SCHEMA_UPLOAD_FILE,
    )
