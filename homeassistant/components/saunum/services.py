"""Define services for the Saunum integration."""

from datetime import timedelta

import probatio
from pysaunum import (
    DEFAULT_DURATION,
    DEFAULT_FAN_DURATION,
    DEFAULT_TEMPERATURE,
    MAX_DURATION,
    MAX_FAN_DURATION,
    MAX_TEMPERATURE,
    MIN_TEMPERATURE,
)

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ATTR_DURATION = "duration"
ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_FAN_DURATION = "fan_duration"

SERVICE_START_SESSION = "start_session"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Saunum integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_START_SESSION,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Optional(
                ATTR_DURATION, default=timedelta(minutes=DEFAULT_DURATION)
            ): probatio.All(
                cv.time_period,
                probatio.Range(
                    min=timedelta(minutes=1),
                    max=timedelta(minutes=MAX_DURATION),
                ),
            ),
            probatio.Optional(
                ATTR_TARGET_TEMPERATURE, default=DEFAULT_TEMPERATURE
            ): probatio.All(
                cv.positive_int,
                probatio.Range(min=MIN_TEMPERATURE, max=MAX_TEMPERATURE),
            ),
            probatio.Optional(
                ATTR_FAN_DURATION, default=timedelta(minutes=DEFAULT_FAN_DURATION)
            ): probatio.All(
                cv.time_period,
                probatio.Range(
                    min=timedelta(minutes=1),
                    max=timedelta(minutes=MAX_FAN_DURATION),
                ),
            ),
        },
        func="async_start_session",
    )
