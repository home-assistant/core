"""Services for Watts Vision integration."""

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_DURATION, DOMAIN, SERVICE_ACTIVATE_TIMER_MODE


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Watts Vision integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ACTIVATE_TIMER_MODE,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            vol.Required(ATTR_TEMPERATURE): vol.Coerce(float),
            vol.Required(ATTR_DURATION): vol.All(
                cv.time_period,
                vol.Range(min=timedelta(minutes=1), max=timedelta(days=1)),
            ),
        },
        func="async_activate_timer_mode",
    )
