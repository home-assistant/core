"""Services for the Viessmann ViCare integration."""

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_SET_VICARE_MODE = "set_vicare_mode"
SERVICE_SET_VICARE_MODE_ATTR_MODE = "vicare_mode"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Viessmann ViCare integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_VICARE_MODE,
        entity_domain=CLIMATE_DOMAIN,
        schema={probatio.Required(SERVICE_SET_VICARE_MODE_ATTR_MODE): cv.string},
        func="set_vicare_mode",
    )
