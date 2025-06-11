"""Support for PlayStation 4 consoles."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import ATTR_COMMAND, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import COMMANDS, DOMAIN, PS4_DATA

SERVICE_COMMAND = "send_command"

PS4_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_COMMAND): vol.In(list(COMMANDS)),
    }
)


async def async_service_command(call: ServiceCall) -> None:
    """Service for sending commands."""
    entity_ids = call.data[ATTR_ENTITY_ID]
    command = call.data[ATTR_COMMAND]
    for device in call.hass.data[PS4_DATA].devices:
        if device.entity_id in entity_ids:
            await device.async_send_command(command)


def register_services(hass: HomeAssistant) -> None:
    """Handle for services."""

    hass.services.async_register(
        DOMAIN, SERVICE_COMMAND, async_service_command, schema=PS4_COMMAND_SCHEMA
    )
