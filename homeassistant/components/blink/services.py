"""Services for the Blink integration."""

from enum import StrEnum

import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class BlinkService(StrEnum):
    """Store keys for Blink services."""

    RECORD = "record"
    TRIGGER_CAMERA = "trigger_camera"
    SAVE_VIDEO = "save_video"
    SAVE_RECENT_CLIPS = "save_recent_clips"


class BlinkServiceArgument(StrEnum):
    """Store keys for Blink service arguments."""

    FILENAME = "filename"
    FILE_PATH = "file_path"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Blink integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BlinkService.RECORD,
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="record",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BlinkService.TRIGGER_CAMERA,
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="trigger_camera",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BlinkService.SAVE_RECENT_CLIPS,
        entity_domain=CAMERA_DOMAIN,
        schema={probatio.Required(BlinkServiceArgument.FILE_PATH): cv.string},
        func="save_recent_clips",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BlinkService.SAVE_VIDEO,
        entity_domain=CAMERA_DOMAIN,
        schema={probatio.Required(BlinkServiceArgument.FILENAME): cv.string},
        func="save_video",
    )
