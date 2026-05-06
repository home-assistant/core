"""Services for Amcrest IP cameras."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_COLOR_BW, CBW, DOMAIN, MOV

_ATTR_PRESET = "preset"
_ATTR_PTZ_MOV = "movement"
_ATTR_PTZ_TT = "travel_time"
_DEFAULT_TT = 0.2


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Amcrest IP Camera services."""
    for service_name, func in (
        ("enable_recording", "async_enable_recording"),
        ("disable_recording", "async_disable_recording"),
        ("enable_audio", "async_enable_audio"),
        ("disable_audio", "async_disable_audio"),
        ("enable_motion_recording", "async_enable_motion_recording"),
        ("disable_motion_recording", "async_disable_motion_recording"),
        ("start_tour", "async_start_tour"),
        ("stop_tour", "async_stop_tour"),
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
        "goto_preset",
        entity_domain=CAMERA_DOMAIN,
        schema={vol.Required(_ATTR_PRESET): vol.All(vol.Coerce(int), vol.Range(min=1))},
        func="async_goto_preset",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_color_bw",
        entity_domain=CAMERA_DOMAIN,
        schema={vol.Required(ATTR_COLOR_BW): vol.In(CBW)},
        func="async_set_color_bw",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "ptz_control",
        entity_domain=CAMERA_DOMAIN,
        schema={
            vol.Required(_ATTR_PTZ_MOV): vol.In(MOV),
            vol.Optional(_ATTR_PTZ_TT, default=_DEFAULT_TT): cv.small_float,
        },
        func="async_ptz_control",
    )
