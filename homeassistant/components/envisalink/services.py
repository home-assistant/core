"""Services for the Envisalink integration."""

import probatio

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_CUSTOM_FUNCTION,
    ATTR_PARTITION,
    DATA_EVL,
    DOMAIN,
    SERVICE_CUSTOM_FUNCTION,
)

SERVICE_ALARM_KEYPRESS = "alarm_keypress"
ATTR_KEYPRESS = "keypress"
ALARM_KEYPRESS_SCHEMA: VolDictType = {probatio.Required(ATTR_KEYPRESS): cv.string}

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
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ALARM_KEYPRESS,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema=ALARM_KEYPRESS_SCHEMA,
        func="async_alarm_keypress",
    )
