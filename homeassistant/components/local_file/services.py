"""Services for the Local file integration."""

from enum import StrEnum

import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class LocalFileService(StrEnum):
    """Store keys for Local file services."""

    UPDATE_FILE_PATH = "update_file_path"


class LocalFileServiceArgument(StrEnum):
    """Store keys for Local file service arguments."""

    FILE_PATH = "file_path"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Local file integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        LocalFileService.UPDATE_FILE_PATH,
        entity_domain=CAMERA_DOMAIN,
        schema={probatio.Required(LocalFileServiceArgument.FILE_PATH): cv.string},
        func="update_file_path",
    )
