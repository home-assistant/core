"""Define services for the Nest integration."""

from enum import StrEnum

import probatio

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class NestService(StrEnum):
    """Store keys for Nest services."""

    SET_FAN_TIMER = "set_fan_timer"


class NestServiceArgument(StrEnum):
    """Store keys for Nest service arguments."""

    DURATION = "duration"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Nest integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NestService.SET_FAN_TIMER,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(NestServiceArgument.DURATION): cv.time_period,
        },
        func="async_set_fan_timer",
        required_features=[ClimateEntityFeature.FAN_MODE],
    )
