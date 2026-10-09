"""Services for the Yardian integration."""

import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN

SERVICE_START_IRRIGATION = "start_irrigation"
SERVICE_SCHEMA_START_IRRIGATION: VolDictType = {
    probatio.Required("duration"): cv.positive_int,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Yardian integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_START_IRRIGATION,
        entity_domain=SWITCH_DOMAIN,
        schema=SERVICE_SCHEMA_START_IRRIGATION,
        func="async_turn_on",
    )
