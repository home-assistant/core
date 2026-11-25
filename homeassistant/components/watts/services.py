"""Services for Watts Vision integration."""

from datetime import timedelta
from enum import StrEnum

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class WattsVisionService(StrEnum):
    """Store keys for Watts Vision services."""

    ACTIVATE_TIMER_MODE = "activate_timer_mode"


class WattsVisionServiceArgument(StrEnum):
    """Store keys for Watts Vision service arguments."""

    TEMPERATURE = "temperature"
    DURATION = "duration"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Watts Vision integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        WattsVisionService.ACTIVATE_TIMER_MODE,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(WattsVisionServiceArgument.TEMPERATURE): probatio.Coerce(
                float
            ),
            probatio.Required(WattsVisionServiceArgument.DURATION): probatio.All(
                cv.time_period,
                probatio.Range(min=timedelta(minutes=1), max=timedelta(days=1)),
            ),
        },
        func="async_activate_timer_mode",
    )
