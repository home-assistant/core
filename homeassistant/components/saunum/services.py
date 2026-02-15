"""Define services for the Saunum integration."""

from __future__ import annotations

from pysaunum import MAX_DURATION, MAX_FAN_DURATION, MAX_TEMPERATURE, MIN_TEMPERATURE
import voluptuous as vol

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
            vol.Optional(ATTR_DURATION, default=120): vol.All(
                cv.positive_int, vol.Range(min=1, max=MAX_DURATION)
            ),
            vol.Optional(ATTR_TARGET_TEMPERATURE, default=80): vol.All(
                cv.positive_int, vol.Range(min=MIN_TEMPERATURE, max=MAX_TEMPERATURE)
            ),
            vol.Optional(ATTR_FAN_DURATION, default=10): vol.All(
                cv.positive_int, vol.Range(min=1, max=MAX_FAN_DURATION)
            ),
        },
        func="async_start_session",
    )
