"""Services for the ONVIF integration."""

import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ABSOLUTE_MOVE,
    ATTR_CONTINUOUS_DURATION,
    ATTR_DISTANCE,
    ATTR_MOVE_MODE,
    ATTR_PAN,
    ATTR_PRESET,
    ATTR_SPEED,
    ATTR_TILT,
    ATTR_ZOOM,
    CONTINUOUS_MOVE,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    DOMAIN,
    GOTOPRESET_MOVE,
    RELATIVE_MOVE,
    SERVICE_PTZ,
    STOP_MOVE,
    ZOOM_IN,
    ZOOM_OUT,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the ONVIF integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_PTZ,
        entity_domain=CAMERA_DOMAIN,
        schema={
            probatio.Optional(ATTR_PAN): probatio.In([DIR_LEFT, DIR_RIGHT]),
            probatio.Optional(ATTR_TILT): probatio.In([DIR_UP, DIR_DOWN]),
            probatio.Optional(ATTR_ZOOM): probatio.In([ZOOM_OUT, ZOOM_IN]),
            probatio.Optional(ATTR_DISTANCE, default=0.1): cv.small_float,
            probatio.Optional(ATTR_SPEED): cv.small_float,
            probatio.Optional(ATTR_MOVE_MODE, default=RELATIVE_MOVE): probatio.In(
                [
                    CONTINUOUS_MOVE,
                    RELATIVE_MOVE,
                    ABSOLUTE_MOVE,
                    GOTOPRESET_MOVE,
                    STOP_MOVE,
                ]
            ),
            probatio.Optional(ATTR_CONTINUOUS_DURATION, default=0.5): cv.small_float,
            probatio.Optional(ATTR_PRESET, default="0"): cv.string,
        },
        func="async_perform_ptz",
    )
