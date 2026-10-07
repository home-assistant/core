"""Services for the Foscam integration."""

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
    SERVICE_PTZ,
    SERVICE_PTZ_PRESET,
)

DEFAULT_TRAVELTIME = 0.125
ATTR_MOVEMENT = "movement"
ATTR_TRAVELTIME = "travel_time"
ATTR_PRESET_NAME = "preset_name"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Foscam integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_PTZ,
        entity_domain=CAMERA_DOMAIN,
        schema={
            probatio.Required(ATTR_MOVEMENT): probatio.In(
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
                ATTR_TRAVELTIME, default=DEFAULT_TRAVELTIME
            ): cv.small_float,
        },
        func="async_perform_ptz",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_PTZ_PRESET,
        entity_domain=CAMERA_DOMAIN,
        schema={probatio.Required(ATTR_PRESET_NAME): cv.string},
        func="async_perform_ptz_preset",
    )
