"""Services for the Blink integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import CONF_FILE_PATH, CONF_FILENAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_RECORD = "record"
SERVICE_TRIGGER = "trigger_camera"
SERVICE_SAVE_VIDEO = "save_video"
SERVICE_SAVE_RECENT_CLIPS = "save_recent_clips"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Blink integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RECORD,
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="record",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_TRIGGER,
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="trigger_camera",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SAVE_RECENT_CLIPS,
        entity_domain=CAMERA_DOMAIN,
        schema={vol.Required(CONF_FILE_PATH): cv.string},
        func="save_recent_clips",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SAVE_VIDEO,
        entity_domain=CAMERA_DOMAIN,
        schema={vol.Required(CONF_FILENAME): cv.string},
        func="save_video",
    )
