"""Services for the motionEye integration."""

from enum import StrEnum

from motioneye_client.const import (
    KEY_TEXT_OVERLAY_CAMERA_NAME,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT,
    KEY_TEXT_OVERLAY_DISABLED,
    KEY_TEXT_OVERLAY_TIMESTAMP,
)
import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class MotionEyeService(StrEnum):
    """Store keys for motionEye services."""

    SET_TEXT_OVERLAY = "set_text_overlay"
    ACTION = "action"
    SNAPSHOT = "snapshot"


class MotionEyeServiceArgument(StrEnum):
    """Store keys for motionEye service arguments."""

    LEFT_TEXT = "left_text"
    CUSTOM_LEFT_TEXT = "custom_left_text"
    RIGHT_TEXT = "right_text"
    CUSTOM_RIGHT_TEXT = "custom_right_text"
    ACTION = "action"


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
                probatio.Optional(
                    MotionEyeServiceArgument.LEFT_TEXT
                ): SCHEMA_TEXT_OVERLAY,
                probatio.Optional(MotionEyeServiceArgument.CUSTOM_LEFT_TEXT): cv.string,
                probatio.Optional(
                    MotionEyeServiceArgument.RIGHT_TEXT
                ): SCHEMA_TEXT_OVERLAY,
                probatio.Optional(
                    MotionEyeServiceArgument.CUSTOM_RIGHT_TEXT
                ): cv.string,
            },
        ),
        probatio.AtLeastOne(
            MotionEyeServiceArgument.LEFT_TEXT,
            MotionEyeServiceArgument.CUSTOM_LEFT_TEXT,
            MotionEyeServiceArgument.RIGHT_TEXT,
            MotionEyeServiceArgument.CUSTOM_RIGHT_TEXT,
        ),
    ),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the motionEye integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MotionEyeService.SET_TEXT_OVERLAY,
        entity_domain=CAMERA_DOMAIN,
        schema=SCHEMA_SERVICE_SET_TEXT,
        func="async_set_text_overlay",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MotionEyeService.ACTION,
        entity_domain=CAMERA_DOMAIN,
        schema={probatio.Required(MotionEyeServiceArgument.ACTION): cv.string},
        func="async_request_action",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MotionEyeService.SNAPSHOT,
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="async_request_snapshot",
    )
