"""Services for the ONVIF integration."""

from enum import StrEnum

import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ABSOLUTE_MOVE,
    CONTINUOUS_MOVE,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    DOMAIN,
    GOTOPRESET_MOVE,
    RELATIVE_MOVE,
    STOP_MOVE,
    ZOOM_IN,
    ZOOM_OUT,
)


class ONVIFService(StrEnum):
    """Store keys for ONVIF services."""

    PTZ = "ptz"


class ONVIFServiceArgument(StrEnum):
    """Store keys for ONVIF service arguments."""

    TILT = "tilt"
    PAN = "pan"
    ZOOM = "zoom"
    DISTANCE = "distance"
    SPEED = "speed"
    CONTINUOUS_DURATION = "continuous_duration"
    PRESET = "preset"
    MOVE_MODE = "move_mode"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the ONVIF integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        ONVIFService.PTZ,
        entity_domain=CAMERA_DOMAIN,
        schema={
            probatio.Optional(ONVIFServiceArgument.PAN): probatio.In(
                [DIR_LEFT, DIR_RIGHT]
            ),
            probatio.Optional(ONVIFServiceArgument.TILT): probatio.In(
                [DIR_UP, DIR_DOWN]
            ),
            probatio.Optional(ONVIFServiceArgument.ZOOM): probatio.In(
                [ZOOM_OUT, ZOOM_IN]
            ),
            probatio.Optional(
                ONVIFServiceArgument.DISTANCE, default=0.1
            ): cv.small_float,
            probatio.Optional(ONVIFServiceArgument.SPEED): cv.small_float,
            probatio.Optional(
                ONVIFServiceArgument.MOVE_MODE, default=RELATIVE_MOVE
            ): probatio.In(
                [
                    CONTINUOUS_MOVE,
                    RELATIVE_MOVE,
                    ABSOLUTE_MOVE,
                    GOTOPRESET_MOVE,
                    STOP_MOVE,
                ]
            ),
            probatio.Optional(
                ONVIFServiceArgument.CONTINUOUS_DURATION, default=0.5
            ): cv.small_float,
            probatio.Optional(ONVIFServiceArgument.PRESET, default="0"): cv.string,
        },
        func="async_perform_ptz",
    )
