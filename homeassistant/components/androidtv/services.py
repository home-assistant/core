"""Services for Android/Fire TV devices."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_COMMAND
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ATTR_ADB_RESPONSE = "adb_response"
ATTR_DEVICE_PATH = "device_path"
ATTR_HDMI_INPUT = "hdmi_input"
ATTR_LOCAL_PATH = "local_path"

SERVICE_ADB_COMMAND = "adb_command"
SERVICE_DOWNLOAD = "download"
SERVICE_LEARN_SENDEVENT = "learn_sendevent"
SERVICE_UPLOAD = "upload"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Android TV / Fire TV services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ADB_COMMAND,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={vol.Required(ATTR_COMMAND): cv.string},
        func="adb_command",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LEARN_SENDEVENT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="learn_sendevent",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DOWNLOAD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Required(ATTR_DEVICE_PATH): cv.string,
            vol.Required(ATTR_LOCAL_PATH): cv.string,
        },
        func="service_download",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UPLOAD,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Required(ATTR_DEVICE_PATH): cv.string,
            vol.Required(ATTR_LOCAL_PATH): cv.string,
        },
        func="service_upload",
    )
