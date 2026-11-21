"""Support for PlayStation 4 consoles."""

from enum import StrEnum

import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import COMMANDS, DOMAIN, PS4_DATA


class PS4Service(StrEnum):
    """Store keys for PlayStation 4 services."""

    SEND_COMMAND = "send_command"


class PS4ServiceArgument(StrEnum):
    """Store keys for PlayStation 4 service arguments."""

    COMMAND = "command"


PS4_COMMAND_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.ENTITY_ID): cv.entity_ids,
        probatio.Required(PS4ServiceArgument.COMMAND): probatio.In(list(COMMANDS)),
    }
)


async def async_service_command(call: ServiceCall) -> None:
    """Service for sending commands."""
    entity_ids = call.data[CommonServiceArgument.ENTITY_ID]
    command = call.data[PS4ServiceArgument.COMMAND]
    for device in call.hass.data[PS4_DATA].devices:
        if device.entity_id in entity_ids:
            await device.async_send_command(command)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Handle for services."""

    hass.services.async_register(
        DOMAIN,
        PS4Service.SEND_COMMAND,
        async_service_command,
        schema=PS4_COMMAND_SCHEMA,
    )
