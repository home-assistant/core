"""Services for the MELCloud integration."""

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    CONF_POSITION,
    DOMAIN,
    SERVICE_SET_VANE_HORIZONTAL,
    SERVICE_SET_VANE_VERTICAL,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the MELCloud integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_VANE_HORIZONTAL,
        entity_domain=CLIMATE_DOMAIN,
        schema={probatio.Required(CONF_POSITION): cv.string},
        func="async_set_vane_horizontal",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_VANE_VERTICAL,
        entity_domain=CLIMATE_DOMAIN,
        schema={probatio.Required(CONF_POSITION): cv.string},
        func="async_set_vane_vertical",
    )
