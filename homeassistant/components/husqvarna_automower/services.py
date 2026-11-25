"""Husqvarna Automower services."""

from datetime import timedelta
from enum import StrEnum

import probatio

from homeassistant.components.lawn_mower import DOMAIN as LAWN_MOWER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, MOW, PARK

OVERRIDE_MODES = [MOW, PARK]


class AutomowerService(StrEnum):
    """Store keys for Husqvarna Automower services."""

    OVERRIDE_SCHEDULE = "override_schedule"
    OVERRIDE_SCHEDULE_WORK_AREA = "override_schedule_work_area"


class AutomowerServiceArgument(StrEnum):
    """Store keys for Husqvarna Automower service arguments."""

    DURATION = "duration"
    OVERRIDE_MODE = "override_mode"
    WORK_AREA_ID = "work_area_id"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        AutomowerService.OVERRIDE_SCHEDULE,
        entity_domain=LAWN_MOWER_DOMAIN,
        schema={
            probatio.Required(AutomowerServiceArgument.OVERRIDE_MODE): probatio.In(
                OVERRIDE_MODES
            ),
            probatio.Required(AutomowerServiceArgument.DURATION): probatio.All(
                cv.time_period,
                cv.positive_timedelta,
                probatio.Range(min=timedelta(minutes=1), max=timedelta(days=42)),
            ),
        },
        func="async_override_schedule",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        AutomowerService.OVERRIDE_SCHEDULE_WORK_AREA,
        entity_domain=LAWN_MOWER_DOMAIN,
        schema={
            probatio.Required(AutomowerServiceArgument.WORK_AREA_ID): probatio.Coerce(
                int
            ),
            probatio.Required(AutomowerServiceArgument.DURATION): probatio.All(
                cv.time_period,
                cv.positive_timedelta,
                probatio.Range(min=timedelta(minutes=1), max=timedelta(days=42)),
            ),
        },
        func="async_override_schedule_work_area",
    )
