"""Roborock services."""

import probatio

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

GET_MAPS_SERVICE_NAME = "get_maps"
SET_VACUUM_ZONED_CLEANING_SERVICE_NAME = "set_vacuum_zoned_cleaning"
SET_VACUUM_GOTO_POSITION_SERVICE_NAME = "set_vacuum_goto_position"
GET_VACUUM_CURRENT_POSITION_SERVICE_NAME = "get_vacuum_current_position"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        GET_MAPS_SERVICE_NAME,
        entity_domain=VACUUM_DOMAIN,
        schema=None,
        func="get_maps",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        GET_VACUUM_CURRENT_POSITION_SERVICE_NAME,
        entity_domain=VACUUM_DOMAIN,
        schema=None,
        func="get_vacuum_current_position",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SET_VACUUM_GOTO_POSITION_SERVICE_NAME,
        entity_domain=VACUUM_DOMAIN,
        schema=cv.make_entity_service_schema(
            {
                probatio.Required("x"): probatio.Coerce(int),
                probatio.Required("y"): probatio.Coerce(int),
            },
        ),
        func="async_set_vacuum_goto_position",
        supports_response=SupportsResponse.NONE,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SET_VACUUM_ZONED_CLEANING_SERVICE_NAME,
        entity_domain=VACUUM_DOMAIN,
        schema=cv.make_entity_service_schema(
            {
                probatio.Required("x1"): probatio.Coerce(int),
                probatio.Required("y1"): probatio.Coerce(int),
                probatio.Required("x2"): probatio.Coerce(int),
                probatio.Required("y2"): probatio.Coerce(int),
                probatio.Required("repeats"): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=0, max=2)
                ),
            },
        ),
        func="async_set_vacuum_zoned_cleaning",
        supports_response=SupportsResponse.NONE,
    )
