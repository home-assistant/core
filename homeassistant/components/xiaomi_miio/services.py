"""Xiaomi services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ATTR_RC_DURATION = "duration"
ATTR_RC_ROTATION = "rotation"
ATTR_RC_VELOCITY = "velocity"
ATTR_ZONE_ARRAY = "zone"
ATTR_ZONE_REPEATER = "repeats"

# Vacuum Services
SERVICE_MOVE_REMOTE_CONTROL = "vacuum_remote_control_move"
SERVICE_MOVE_REMOTE_CONTROL_STEP = "vacuum_remote_control_move_step"
SERVICE_START_REMOTE_CONTROL = "vacuum_remote_control_start"
SERVICE_STOP_REMOTE_CONTROL = "vacuum_remote_control_stop"
SERVICE_CLEAN_SEGMENT = "vacuum_clean_segment"
SERVICE_CLEAN_ZONE = "vacuum_clean_zone"
SERVICE_GOTO = "vacuum_goto"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    # Vacuum Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_START_REMOTE_CONTROL,
        entity_domain=VACUUM_DOMAIN,
        schema=None,
        func="async_remote_control_start",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_STOP_REMOTE_CONTROL,
        entity_domain=VACUUM_DOMAIN,
        schema=None,
        func="async_remote_control_stop",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_MOVE_REMOTE_CONTROL,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Optional(ATTR_RC_VELOCITY): vol.All(
                vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
            ),
            vol.Optional(ATTR_RC_ROTATION): vol.All(
                vol.Coerce(int), vol.Clamp(min=-179, max=179)
            ),
            vol.Optional(ATTR_RC_DURATION): cv.positive_int,
        },
        func="async_remote_control_move",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_MOVE_REMOTE_CONTROL_STEP,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Optional(ATTR_RC_VELOCITY): vol.All(
                vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
            ),
            vol.Optional(ATTR_RC_ROTATION): vol.All(
                vol.Coerce(int), vol.Clamp(min=-179, max=179)
            ),
            vol.Optional(ATTR_RC_DURATION): cv.positive_int,
        },
        func="async_remote_control_move_step",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAN_ZONE,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Required(ATTR_ZONE_ARRAY): vol.All(
                list,
                [
                    vol.ExactSequence(
                        [
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                        ]
                    )
                ],
            ),
            vol.Required(ATTR_ZONE_REPEATER): vol.All(
                vol.Coerce(int), vol.Clamp(min=1, max=3)
            ),
        },
        func="async_clean_zone",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GOTO,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Required("x_coord"): vol.Coerce(int),
            vol.Required("y_coord"): vol.Coerce(int),
        },
        func="async_goto",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAN_SEGMENT,
        entity_domain=VACUUM_DOMAIN,
        schema={vol.Required("segments"): vol.Any(vol.Coerce(int), [vol.Coerce(int)])},
        func="async_clean_segment",
    )
