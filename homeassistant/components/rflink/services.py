"""Services for the Rflink integration."""

from enum import StrEnum
import logging

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, EVENT_KEY_COMMAND, EVENT_KEY_ID, SIGNAL_EVENT
from .entity import RflinkCommand

_LOGGER = logging.getLogger(__name__)


class RflinkService(StrEnum):
    """Store keys for Rflink services."""

    SEND_COMMAND = "send_command"


class RflinkServiceArgument(StrEnum):
    """Store keys for Rflink service arguments."""

    COMMAND = "command"
    DEVICE_ID = "device_id"


SEND_COMMAND_SCHEMA = probatio.Schema(
    {
        probatio.Required(RflinkServiceArgument.DEVICE_ID): cv.string,
        probatio.Required(RflinkServiceArgument.COMMAND): cv.string,
    }
)


async def _async_send_command(call: ServiceCall) -> None:
    """Send Rflink command."""
    _LOGGER.debug("Rflink command for %s", str(call.data))
    if not (
        await RflinkCommand.send_command(
            call.data.get(RflinkServiceArgument.DEVICE_ID),
            call.data.get(RflinkServiceArgument.COMMAND),
        )
    ):
        _LOGGER.error("Failed Rflink command for %s", str(call.data))
    else:
        async_dispatcher_send(
            call.hass,
            SIGNAL_EVENT,
            {
                EVENT_KEY_ID: call.data.get(RflinkServiceArgument.DEVICE_ID),
                EVENT_KEY_COMMAND: call.data.get(RflinkServiceArgument.COMMAND),
            },
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Rflink integration."""
    hass.services.async_register(
        DOMAIN,
        RflinkService.SEND_COMMAND,
        _async_send_command,
        schema=SEND_COMMAND_SCHEMA,
    )
