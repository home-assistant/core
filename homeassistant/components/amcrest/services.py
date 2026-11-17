"""Services for Amcrest IP cameras."""

from enum import StrEnum

import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import CBW, DOMAIN, MOV

_DEFAULT_TT = 0.2


class AmcrestService(StrEnum):
    """Store keys for Amcrest services."""

    ENABLE_RECORDING = "enable_recording"
    DISABLE_RECORDING = "disable_recording"
    ENABLE_AUDIO = "enable_audio"
    DISABLE_AUDIO = "disable_audio"
    ENABLE_MOTION_RECORDING = "enable_motion_recording"
    DISABLE_MOTION_RECORDING = "disable_motion_recording"
    GOTO_PRESET = "goto_preset"
    SET_COLOR_BW = "set_color_bw"
    START_TOUR = "start_tour"
    STOP_TOUR = "stop_tour"
    PTZ_CONTROL = "ptz_control"


class AmcrestServiceArgument(StrEnum):
    """Store keys for Amcrest service arguments."""

    PRESET = "preset"
    COLOR_BW = "color_bw"
    MOVEMENT = "movement"
    TRAVEL_TIME = "travel_time"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Amcrest IP Camera services."""
    for service_name, func in (
        (AmcrestService.ENABLE_RECORDING, "async_enable_recording"),
        (AmcrestService.DISABLE_RECORDING, "async_disable_recording"),
        (AmcrestService.ENABLE_AUDIO, "async_enable_audio"),
        (AmcrestService.DISABLE_AUDIO, "async_disable_audio"),
        (AmcrestService.ENABLE_MOTION_RECORDING, "async_enable_motion_recording"),
        (AmcrestService.DISABLE_MOTION_RECORDING, "async_disable_motion_recording"),
        (AmcrestService.START_TOUR, "async_start_tour"),
        (AmcrestService.STOP_TOUR, "async_stop_tour"),
    ):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            service_name,
            entity_domain=CAMERA_DOMAIN,
            schema=None,
            func=func,
        )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        AmcrestService.GOTO_PRESET,
        entity_domain=CAMERA_DOMAIN,
        schema={
            probatio.Required(AmcrestServiceArgument.PRESET): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1)
            )
        },
        func="async_goto_preset",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        AmcrestService.SET_COLOR_BW,
        entity_domain=CAMERA_DOMAIN,
        schema={probatio.Required(AmcrestServiceArgument.COLOR_BW): probatio.In(CBW)},
        func="async_set_color_bw",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        AmcrestService.PTZ_CONTROL,
        entity_domain=CAMERA_DOMAIN,
        schema={
            probatio.Required(AmcrestServiceArgument.MOVEMENT): probatio.In(MOV),
            probatio.Optional(
                AmcrestServiceArgument.TRAVEL_TIME, default=_DEFAULT_TT
            ): cv.small_float,
        },
        func="async_ptz_control",
    )
