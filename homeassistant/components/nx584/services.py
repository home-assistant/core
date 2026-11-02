"""Services for the NX584 integration."""

import probatio

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_BYPASS_ZONE = "bypass_zone"
SERVICE_UNBYPASS_ZONE = "unbypass_zone"
ATTR_ZONE = "zone"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the NX584 integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_BYPASS_ZONE,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema={probatio.Required(ATTR_ZONE): cv.positive_int},
        func="alarm_bypass",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UNBYPASS_ZONE,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema={probatio.Required(ATTR_ZONE): cv.positive_int},
        func="alarm_unbypass",
    )
