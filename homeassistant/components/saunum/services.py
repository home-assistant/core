"""Define services for the Saunum integration."""

from datetime import timedelta
from enum import StrEnum

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


class LeilSaunaService(StrEnum):
    """Store keys for Saunum services."""

    START_SESSION = "start_session"


class LeilSaunaServiceArgument(StrEnum):
    """Store keys for Saunum service arguments."""

    DURATION = "duration"
    TARGET_TEMPERATURE = "target_temperature"
    FAN_DURATION = "fan_duration"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Saunum integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        LeilSaunaService.START_SESSION,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Optional(
                LeilSaunaServiceArgument.DURATION,
                default=timedelta(minutes=DEFAULT_DURATION),
            ): probatio.All(
                cv.time_period,
                probatio.Range(
                    min=timedelta(minutes=1),
                    max=timedelta(minutes=MAX_DURATION),
                ),
            ),
            probatio.Optional(
                LeilSaunaServiceArgument.TARGET_TEMPERATURE, default=DEFAULT_TEMPERATURE
            ): probatio.All(
                cv.positive_int,
                probatio.Range(min=MIN_TEMPERATURE, max=MAX_TEMPERATURE),
            ),
            probatio.Optional(
                LeilSaunaServiceArgument.FAN_DURATION,
                default=timedelta(minutes=DEFAULT_FAN_DURATION),
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
