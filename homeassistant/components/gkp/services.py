"""Services for GKP integration."""

from datetime import timedelta

from gkphomepython.const import BOOST_DURATION_MAX, BOOST_DURATION_MIN
import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_DURATION, DOMAIN, SERVICE_ACTIVATE_BOOST


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the GKP integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ACTIVATE_BOOST,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(ATTR_TEMPERATURE): probatio.Coerce(float),
            probatio.Required(ATTR_DURATION): probatio.All(
                cv.time_period,
                probatio.Range(
                    min=timedelta(minutes=BOOST_DURATION_MIN),
                    max=timedelta(minutes=BOOST_DURATION_MAX),
                ),
            ),
        },
        func="async_activate_boost",
    )
