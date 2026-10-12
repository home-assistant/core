"""Services for the Envisalink integration."""

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CUSTOM_FUNCTION,
    ATTR_PARTITION,
    DATA_EVL,
    DOMAIN,
    SERVICE_CUSTOM_FUNCTION,
)

SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CUSTOM_FUNCTION): cv.string,
        probatio.Required(ATTR_PARTITION): cv.string,
    }
)


async def _handle_custom_function(call: ServiceCall) -> None:
    """Handle custom/PGM service."""
    data = call.hass.data[DATA_EVL]
    custom_function = call.data.get(ATTR_CUSTOM_FUNCTION)
    partition = call.data.get(ATTR_PARTITION)
    data.controller.command_output(data.code, partition, custom_function)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Envisalink integration."""
    hass.services.async_register(
        DOMAIN, SERVICE_CUSTOM_FUNCTION, _handle_custom_function, schema=SERVICE_SCHEMA
    )
