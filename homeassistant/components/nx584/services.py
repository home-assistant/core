"""Services for the NX584 integration."""

from enum import StrEnum

import probatio

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class NX584Service(StrEnum):
    """Store keys for NX584 services."""

    BYPASS_ZONE = "bypass_zone"
    UNBYPASS_ZONE = "unbypass_zone"


class NX584ServiceArgument(StrEnum):
    """Store keys for NX584 service arguments."""

    ZONE = "zone"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the NX584 integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NX584Service.BYPASS_ZONE,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema={probatio.Required(NX584ServiceArgument.ZONE): cv.positive_int},
        func="alarm_bypass",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NX584Service.UNBYPASS_ZONE,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema={probatio.Required(NX584ServiceArgument.ZONE): cv.positive_int},
        func="alarm_unbypass",
    )
