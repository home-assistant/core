"""Service handlers for the Evohome integration."""

from datetime import timedelta
from typing import Any, Final

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, EvoService, EvoServiceArgument

# Controller service schemas (registered as entity services)
SET_SYSTEM_MODE_SCHEMA: Final[dict[str | probatio.Marker, Any]] = {
    # unsupported modes are rejected at runtime with ServiceValidationError
    # ... so, don't use SystemMode enum here
    probatio.Required(EvoServiceArgument.MODE): cv.string,
    probatio.Exclusive(EvoServiceArgument.DURATION, "temporary"): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(hours=0), max=timedelta(hours=24)),
    ),
    probatio.Exclusive(EvoServiceArgument.PERIOD, "temporary"): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(days=1), max=timedelta(days=99)),
    ),
}

# Zone service schemas (registered as entity services)
SET_ZONE_OVERRIDE_SCHEMA: Final[dict[str | probatio.Marker, Any]] = {
    probatio.Required(EvoServiceArgument.SETPOINT): probatio.All(
        probatio.Coerce(float), probatio.Range(min=4.0, max=35.0)
    ),
    probatio.Optional(EvoServiceArgument.DURATION): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(days=0), max=timedelta(days=1)),
    ),
}

# DHW service schemas (registered as entity services)
SET_DHW_OVERRIDE_SCHEMA: Final[dict[str | probatio.Marker, Any]] = {
    probatio.Required(EvoServiceArgument.STATE): cv.boolean,
    probatio.Optional(EvoServiceArgument.DURATION): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(days=0), max=timedelta(days=1)),
    ),
}


def _register_ctl_entity_services(hass: HomeAssistant) -> None:
    """Register entity-level services for controllers."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.SET_SYSTEM_MODE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_SYSTEM_MODE_SCHEMA,
        func="async_set_system_mode",
    )


def _register_zone_entity_services(hass: HomeAssistant) -> None:
    """Register entity-level services for zones."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.SET_ZONE_OVERRIDE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_ZONE_OVERRIDE_SCHEMA,
        func="async_set_zone_override",
    )


def _register_dhw_entity_services(hass: HomeAssistant) -> None:
    """Register entity-level services for DHW zones."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.SET_DHW_OVERRIDE,
        entity_domain=WATER_HEATER_DOMAIN,
        schema=SET_DHW_OVERRIDE_SCHEMA,
        func="async_set_dhw_override",
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Evohome services."""

    _register_ctl_entity_services(hass)
    _register_zone_entity_services(hass)
    _register_dhw_entity_services(hass)
