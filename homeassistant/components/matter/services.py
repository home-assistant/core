"""Services for Matter devices."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

# vacuum entity service attributes
ATTR_CURRENT_AREA = "current_area"
ATTR_CURRENT_AREA_NAME = "current_area_name"
ATTR_SELECTED_AREAS = "selected_areas"
# water heater entity service attributes
ATTR_DURATION = "duration"
ATTR_EMERGENCY_BOOST = "emergency_boost"
ATTR_TEMPORARY_SETPOINT = "temporary_setpoint"

# vacuum entity service actions
SERVICE_GET_AREAS = "get_areas"  # get SupportedAreas and SupportedMaps
SERVICE_CLEAN_AREAS = "clean_areas"  # call SelectAreas Matter command and start RVC
# water heater entity service actions
SERVICE_WATER_HEATER_BOOST = "water_heater_boost"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Matter services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_WATER_HEATER_BOOST,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            # duration >=1
            vol.Required(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(ATTR_EMERGENCY_BOOST): cv.boolean,
            vol.Optional(ATTR_TEMPORARY_SETPOINT): vol.All(
                vol.Coerce(int), vol.Range(min=30, max=65)
            ),
        },
        func="async_set_boost",
    )

    # SERVICE_CLEAN_AREAS
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAN_AREAS,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Required("areas"): vol.All(cv.ensure_list, [cv.positive_int]),
        },
        func="async_clean_areas",
    )

    # SERVICE_GET_AREAS
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_AREAS,
        entity_domain=VACUUM_DOMAIN,
        schema={},
        func="async_get_areas",
        supports_response=SupportsResponse.ONLY,
    )
