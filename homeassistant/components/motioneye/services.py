"""Services for the motionEye integration."""

from motioneye_client.const import (
    KEY_TEXT_OVERLAY_CAMERA_NAME,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT,
    KEY_TEXT_OVERLAY_DISABLED,
    KEY_TEXT_OVERLAY_LEFT,
    KEY_TEXT_OVERLAY_RIGHT,
    KEY_TEXT_OVERLAY_TIMESTAMP,
)
import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import CONF_ACTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, SERVICE_ACTION, SERVICE_SET_TEXT_OVERLAY, SERVICE_SNAPSHOT

SCHEMA_TEXT_OVERLAY = probatio.In(
    [
        KEY_TEXT_OVERLAY_DISABLED,
        KEY_TEXT_OVERLAY_TIMESTAMP,
        KEY_TEXT_OVERLAY_CUSTOM_TEXT,
        KEY_TEXT_OVERLAY_CAMERA_NAME,
    ]
)
SCHEMA_SERVICE_SET_TEXT = probatio.Schema(
    probatio.All(
        cv.make_entity_service_schema(
            {
                probatio.Optional(KEY_TEXT_OVERLAY_LEFT): SCHEMA_TEXT_OVERLAY,
                probatio.Optional(KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT): cv.string,
                probatio.Optional(KEY_TEXT_OVERLAY_RIGHT): SCHEMA_TEXT_OVERLAY,
                probatio.Optional(KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT): cv.string,
            },
        ),
        probatio.AtLeastOne(
            KEY_TEXT_OVERLAY_LEFT,
            KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT,
            KEY_TEXT_OVERLAY_RIGHT,
            KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT,
        ),
    ),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the motionEye integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_TEXT_OVERLAY,
        entity_domain=CAMERA_DOMAIN,
        schema=SCHEMA_SERVICE_SET_TEXT,
        func="async_set_text_overlay",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ACTION,
        entity_domain=CAMERA_DOMAIN,
        schema={probatio.Required(CONF_ACTION): cv.string},
        func="async_request_action",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SNAPSHOT,
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="async_request_snapshot",
    )
