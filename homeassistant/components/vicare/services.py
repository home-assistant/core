"""Services for the Viessmann ViCare integration."""

from datetime import time
from typing import Any

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_SET_VICARE_MODE = "set_vicare_mode"
SERVICE_SET_VICARE_MODE_ATTR_MODE = "vicare_mode"

SERVICE_GET_CIRCULATION_SCHEDULE = "get_circulation_schedule"
SERVICE_SET_CIRCULATION_SCHEDULE = "set_circulation_schedule"

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

ATTR_FROM = "from"
ATTR_TO = "to"


def _slot_time(value: Any) -> time:
    """Parse a slot time on a 10-minute grid, 24:00 is the end of the day."""
    if isinstance(value, str) and value in ("24:00", "24:00:00"):
        return time.max
    parsed = cv.time(value)
    if parsed.second or parsed.microsecond or parsed.minute % 10:
        raise probatio.Invalid(f"Time must be on a 10-minute grid: {value}")
    return parsed


def _validate_slot(slot: dict[str, Any]) -> dict[str, Any]:
    """Validate that a slot ends after it starts."""
    if slot[ATTR_TO] <= slot[ATTR_FROM]:
        raise probatio.Invalid(
            f"End time {slot[ATTR_TO]} must be after start time {slot[ATTR_FROM]}"
        )
    return slot


CIRCULATION_SCHEDULE_SLOT_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Required(ATTR_FROM): _slot_time,
            probatio.Required(ATTR_TO): _slot_time,
            probatio.Required(ATTR_MODE): cv.string,
        }
    ),
    _validate_slot,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Viessmann ViCare integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_VICARE_MODE,
        entity_domain=CLIMATE_DOMAIN,
        schema={probatio.Required(SERVICE_SET_VICARE_MODE_ATTR_MODE): cv.string},
        func="set_vicare_mode",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_CIRCULATION_SCHEDULE,
        entity_domain=WATER_HEATER_DOMAIN,
        schema=None,
        func="get_circulation_schedule",
        supports_response=SupportsResponse.ONLY,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_CIRCULATION_SCHEDULE,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            probatio.Optional(day): probatio.All(
                probatio.EnsureList(), [CIRCULATION_SCHEDULE_SLOT_SCHEMA]
            )
            for day in WEEKDAYS
        },
        func="set_circulation_schedule",
    )
