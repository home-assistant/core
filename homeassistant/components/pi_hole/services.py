"""Services for the Pi-hole integration."""

import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, SERVICE_DISABLE, SERVICE_DISABLE_ATTR_DURATION


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Pi-hole integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DISABLE,
        entity_domain=SWITCH_DOMAIN,
        schema={
            probatio.Required(SERVICE_DISABLE_ATTR_DURATION): probatio.All(
                cv.time_period_str, cv.positive_timedelta
            )
        },
        func="async_disable",
    )
