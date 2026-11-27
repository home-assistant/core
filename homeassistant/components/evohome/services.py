"""Service handlers for the Evohome integration."""

from datetime import datetime, timedelta
from typing import Any, Final

from evohomeasync2.const import (
    SZ_DAY_OF_WEEK,
    SZ_HEAT_SETPOINT,
    SZ_SWITCHPOINTS,
    SZ_TIME_OF_DAY,
)
import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
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

DAYS_OF_WEEK: Final = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _time_of_day(value: Any) -> str:
    """Validate a switchpoint time ("HH:MM" or "HH:MM:00") as "HH:MM:00"."""
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            time = datetime.strptime(str(value), fmt)
        except ValueError:
            continue
        if time.second:
            break
        return time.strftime("%H:%M:00")
    raise probatio.Invalid(f"invalid time_of_day '{value}', expected HH:MM")


def _one_entry_per_day(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate that a schedule has exactly one entry for every day of the week."""
    if sorted(day[SZ_DAY_OF_WEEK] for day in days) != sorted(DAYS_OF_WEEK):
        raise probatio.Invalid(
            "the schedule must have exactly one entry for each day, Monday to Sunday"
        )
    return sorted(days, key=lambda day: DAYS_OF_WEEK.index(day[SZ_DAY_OF_WEEK]))


SWITCHPOINT_SCHEMA: Final = probatio.Schema(
    {
        probatio.Required(SZ_TIME_OF_DAY): _time_of_day,
        probatio.Required(SZ_HEAT_SETPOINT): probatio.All(
            probatio.Coerce(float), probatio.Range(min=4.0, max=35.0)
        ),
    }
)

DAY_SCHEDULE_SCHEMA: Final = probatio.Schema(
    {
        probatio.Required(SZ_DAY_OF_WEEK): probatio.All(
            cv.string, str.capitalize, probatio.In(DAYS_OF_WEEK)
        ),
        probatio.Required(SZ_SWITCHPOINTS): probatio.All(
            [SWITCHPOINT_SCHEMA], probatio.Length(min=1)
        ),
    }
)

SET_ZONE_SCHEDULE_SCHEMA: Final[dict[str | probatio.Marker, Any]] = {
    probatio.Required(EvoServiceArgument.SCHEDULE): probatio.All(
        [DAY_SCHEDULE_SCHEMA], _one_entry_per_day
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

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.GET_ZONE_SCHEDULE,
        entity_domain=CLIMATE_DOMAIN,
        schema=None,
        func="async_get_zone_schedule",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.SET_ZONE_SCHEDULE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_ZONE_SCHEDULE_SCHEMA,
        func="async_set_zone_schedule",
        supports_response=SupportsResponse.OPTIONAL,
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
