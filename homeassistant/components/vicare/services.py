"""Services for the Viessmann ViCare integration."""

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
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

# The time selector sends seconds, ViCare only accepts HH:MM on a 10-minute grid.
_SLOT_TIME = probatio.All(
    cv.string,
    probatio.Match(r"^(?:[01]\d|2[0-3]):[0-5]0(?::00)?$|^24:00$"),
    lambda value: value[:5],
)

CIRCULATION_SCHEDULE_SLOT_SCHEMA = probatio.Schema(
    {
        probatio.Required("start"): _SLOT_TIME,
        probatio.Required("end"): _SLOT_TIME,
        probatio.Required("mode"): cv.string,
    }
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
