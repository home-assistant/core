"""Support for Envisalink devices."""

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DATA_EVL, DOMAIN

SERVICE_CUSTOM_FUNCTION = "invoke_custom_function"
ATTR_CUSTOM_FUNCTION = "pgm"
ATTR_PARTITION = "partition"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CUSTOM_FUNCTION): cv.string,
        vol.Required(ATTR_PARTITION): cv.string,
    }
)


async def _handle_custom_function(call: ServiceCall) -> None:
    """Handle custom/PGM service."""
    custom_function = call.data.get(ATTR_CUSTOM_FUNCTION)
    partition = call.data.get(ATTR_PARTITION)
    controller = call.hass.data[DATA_EVL].controller
    controller.command_output(call.hass.data[DATA_EVL].code, partition, custom_function)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    hass.services.async_register(
        DOMAIN, SERVICE_CUSTOM_FUNCTION, _handle_custom_function, schema=SERVICE_SCHEMA
    )
