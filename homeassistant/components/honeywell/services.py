"""Services for the Honeywell integration."""

from enum import StrEnum

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class HoneywellService(StrEnum):
    """Store keys for Honeywell services."""

    SET_HOLD_UNTIL = "set_hold_until"


class HoneywellServiceArgument(StrEnum):
    """Store keys for Honeywell service arguments."""

    TEMPERATURE = "temperature"
    UNTIL = "until"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Honeywell integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        HoneywellService.SET_HOLD_UNTIL,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(HoneywellServiceArgument.UNTIL): cv.time,
            probatio.Optional(HoneywellServiceArgument.TEMPERATURE): probatio.Coerce(
                float
            ),
        },
        func="async_set_hold_until",
    )
