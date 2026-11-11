"""Services for the Hayward Omnilogic integration."""

from enum import StrEnum

import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class OmniLogicService(StrEnum):
    """Store keys for Hayward Omnilogic services."""

    SET_PUMP_SPEED = "set_pump_speed"


class OmniLogicServiceArgument(StrEnum):
    """Store keys for Hayward Omnilogic service arguments."""

    SPEED = "speed"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Hayward Omnilogic integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        OmniLogicService.SET_PUMP_SPEED,
        entity_domain=SWITCH_DOMAIN,
        schema={probatio.Required(OmniLogicServiceArgument.SPEED): cv.positive_int},
        func="async_set_speed",
    )
