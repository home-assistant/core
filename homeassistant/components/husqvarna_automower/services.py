"""Husqvarna Automower services."""

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.lawn_mower import DOMAIN as LAWN_MOWER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, MOW, PARK

OVERRIDE_MODES = [MOW, PARK]


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "override_schedule",
        entity_domain=LAWN_MOWER_DOMAIN,
        schema={
            vol.Required("override_mode"): vol.In(OVERRIDE_MODES),
            vol.Required("duration"): vol.All(
                cv.time_period,
                cv.positive_timedelta,
                vol.Range(min=timedelta(minutes=1), max=timedelta(days=42)),
            ),
        },
        func="async_override_schedule",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "override_schedule_work_area",
        entity_domain=LAWN_MOWER_DOMAIN,
        schema={
            vol.Required("work_area_id"): vol.Coerce(int),
            vol.Required("duration"): vol.All(
                cv.time_period,
                cv.positive_timedelta,
                vol.Range(min=timedelta(minutes=1), max=timedelta(days=42)),
            ),
        },
        func="async_override_schedule_work_area",
    )
