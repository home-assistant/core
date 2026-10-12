"""Services for the Hayward Omnilogic integration."""

import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_SET_SPEED = "set_pump_speed"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Hayward Omnilogic integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_SPEED,
        entity_domain=SWITCH_DOMAIN,
        schema={probatio.Required("speed"): cv.positive_int},
        func="async_set_speed",
    )
