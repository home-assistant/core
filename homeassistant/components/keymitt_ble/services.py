"""Services for the Keymitt MicroBot Push integration."""

import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN

CALIBRATE = "calibrate"
CALIBRATE_SCHEMA: VolDictType = {
    probatio.Required("depth"): cv.positive_int,
    probatio.Required("duration"): cv.positive_int,
    probatio.Required("mode"): probatio.In(["normal", "invert", "toggle"]),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Keymitt MicroBot Push integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        CALIBRATE,
        entity_domain=SWITCH_DOMAIN,
        schema=CALIBRATE_SCHEMA,
        func="async_calibrate",
    )
