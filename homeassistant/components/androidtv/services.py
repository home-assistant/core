"""Services for Android/Fire TV devices."""

from enum import StrEnum

import probatio

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ATTR_ADB_RESPONSE = "adb_response"
ATTR_HDMI_INPUT = "hdmi_input"


class AndroidTVService(StrEnum):
    """Store keys for Android TV services."""

    ADB_COMMAND = "adb_command"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    LEARN_SENDEVENT = "learn_sendevent"


class AndroidTVServiceArgument(StrEnum):
    """Store keys for Android TV service arguments."""

    COMMAND = "command"
    DEVICE_PATH = "device_path"
    LOCAL_PATH = "local_path"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Android TV / Fire TV services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        AndroidTVService.ADB_COMMAND,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={probatio.Required(AndroidTVServiceArgument.COMMAND): cv.string},
        func="adb_command",
        supports_response=SupportsResponse.OPTIONAL,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        AndroidTVService.LEARN_SENDEVENT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="learn_sendevent",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        AndroidTVService.DOWNLOAD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(AndroidTVServiceArgument.DEVICE_PATH): cv.string,
            probatio.Required(AndroidTVServiceArgument.LOCAL_PATH): cv.string,
        },
        func="service_download",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        AndroidTVService.UPLOAD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            probatio.Required(AndroidTVServiceArgument.DEVICE_PATH): cv.string,
            probatio.Required(AndroidTVServiceArgument.LOCAL_PATH): cv.string,
        },
        func="service_upload",
    )
