"""Services for the Foscam integration."""

from enum import StrEnum

import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    DIR_BOTTOMLEFT,
    DIR_BOTTOMRIGHT,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_TOPLEFT,
    DIR_TOPRIGHT,
    DIR_UP,
    DOMAIN,
)

DEFAULT_TRAVELTIME = 0.125


class FoscamService(StrEnum):
    """Store keys for Foscam services."""

    PTZ = "ptz"
    PTZ_PRESET = "ptz_preset"


class FoscamServiceArgument(StrEnum):
    """Store keys for Foscam service arguments."""

    MOVEMENT = "movement"
    TRAVEL_TIME = "travel_time"
    PRESET_NAME = "preset_name"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Foscam integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        FoscamService.PTZ,
        entity_domain=CAMERA_DOMAIN,
        schema={
            probatio.Required(FoscamServiceArgument.MOVEMENT): probatio.In(
                [
                    DIR_UP,
                    DIR_DOWN,
                    DIR_LEFT,
                    DIR_RIGHT,
                    DIR_TOPLEFT,
                    DIR_TOPRIGHT,
                    DIR_BOTTOMLEFT,
                    DIR_BOTTOMRIGHT,
                ]
            ),
            probatio.Optional(
                FoscamServiceArgument.TRAVEL_TIME, default=DEFAULT_TRAVELTIME
            ): cv.small_float,
        },
        func="async_perform_ptz",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        FoscamService.PTZ_PRESET,
        entity_domain=CAMERA_DOMAIN,
        schema={probatio.Required(FoscamServiceArgument.PRESET_NAME): cv.string},
        func="async_perform_ptz_preset",
    )
