"""Roborock services."""

from enum import StrEnum

import probatio

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class RoborockService(StrEnum):
    """Store keys for Roborock services."""

    GET_MAPS = "get_maps"
    GET_VACUUM_CURRENT_POSITION = "get_vacuum_current_position"
    SET_VACUUM_GOTO_POSITION = "set_vacuum_goto_position"
    SET_VACUUM_ZONED_CLEANING = "set_vacuum_zoned_cleaning"


class RoborockServiceArgument(StrEnum):
    """Store keys for Roborock service arguments."""

    REPEATS = "repeats"
    X = "x"
    X1 = "x1"
    X2 = "x2"
    Y = "y"
    Y1 = "y1"
    Y2 = "y2"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        RoborockService.GET_MAPS,
        entity_domain=VACUUM_DOMAIN,
        schema=None,
        func="get_maps",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        RoborockService.GET_VACUUM_CURRENT_POSITION,
        entity_domain=VACUUM_DOMAIN,
        schema=None,
        func="get_vacuum_current_position",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        RoborockService.SET_VACUUM_GOTO_POSITION,
        entity_domain=VACUUM_DOMAIN,
        schema=cv.make_entity_service_schema(
            {
                probatio.Required(RoborockServiceArgument.X): probatio.Coerce(int),
                probatio.Required(RoborockServiceArgument.Y): probatio.Coerce(int),
            },
        ),
        func="async_set_vacuum_goto_position",
        supports_response=SupportsResponse.NONE,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        RoborockService.SET_VACUUM_ZONED_CLEANING,
        entity_domain=VACUUM_DOMAIN,
        schema=cv.make_entity_service_schema(
            {
                probatio.Required(RoborockServiceArgument.X1): probatio.Coerce(int),
                probatio.Required(RoborockServiceArgument.Y1): probatio.Coerce(int),
                probatio.Required(RoborockServiceArgument.X2): probatio.Coerce(int),
                probatio.Required(RoborockServiceArgument.Y2): probatio.Coerce(int),
                probatio.Required(RoborockServiceArgument.REPEATS): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=0, max=2)
                ),
            },
        ),
        func="async_set_vacuum_zoned_cleaning",
        supports_response=SupportsResponse.NONE,
    )
