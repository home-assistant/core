"""Services for the Keymitt MicroBot Push integration."""

from enum import StrEnum

import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class MicroBotService(StrEnum):
    """Store keys for Keymitt MicroBot Push services."""

    CALIBRATE = "calibrate"


class MicroBotServiceArgument(StrEnum):
    """Store keys for Keymitt MicroBot Push service arguments."""

    DEPTH = "depth"
    DURATION = "duration"
    MODE = "mode"


CALIBRATE_SCHEMA: VolDictType = {
    probatio.Required(MicroBotServiceArgument.DEPTH): cv.positive_int,
    probatio.Required(MicroBotServiceArgument.DURATION): cv.positive_int,
    probatio.Required(MicroBotServiceArgument.MODE): probatio.In(
        ["normal", "invert", "toggle"]
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Keymitt MicroBot Push integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MicroBotService.CALIBRATE,
        entity_domain=SWITCH_DOMAIN,
        schema=CALIBRATE_SCHEMA,
        func="async_calibrate",
    )
