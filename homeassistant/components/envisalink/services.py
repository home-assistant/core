"""Services for the Envisalink integration."""

from enum import StrEnum

import probatio

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import VolDictType

from .const import DATA_EVL, DOMAIN


class EnvisalinkService(StrEnum):
    """Store keys for Envisalink services."""

    ALARM_KEYPRESS = "alarm_keypress"
    INVOKE_CUSTOM_FUNCTION = "invoke_custom_function"


class EnvisalinkServiceArgument(StrEnum):
    """Store keys for Envisalink service arguments."""

    KEYPRESS = "keypress"
    PARTITION = "partition"
    PGM = "pgm"


ALARM_KEYPRESS_SCHEMA: VolDictType = {
    probatio.Required(EnvisalinkServiceArgument.KEYPRESS): cv.string
}

SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(EnvisalinkServiceArgument.PGM): cv.string,
        probatio.Required(EnvisalinkServiceArgument.PARTITION): cv.string,
    }
)


async def _handle_custom_function(call: ServiceCall) -> None:
    """Handle custom/PGM service."""
    data = call.hass.data[DATA_EVL]
    custom_function = call.data.get(EnvisalinkServiceArgument.PGM)
    partition = call.data.get(EnvisalinkServiceArgument.PARTITION)
    data.controller.command_output(data.code, partition, custom_function)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Envisalink integration."""
    hass.services.async_register(
        DOMAIN,
        EnvisalinkService.INVOKE_CUSTOM_FUNCTION,
        _handle_custom_function,
        schema=SERVICE_SCHEMA,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        EnvisalinkService.ALARM_KEYPRESS,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema=ALARM_KEYPRESS_SCHEMA,
        func="async_alarm_keypress",
    )
