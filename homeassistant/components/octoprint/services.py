"""Services for octoprint."""

from enum import StrEnum
from typing import cast

import probatio
from pyoctoprintapi import OctoprintClient

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .coordinator import OctoprintConfigEntry


class OctoPrintService(StrEnum):
    """Store keys for OctoPrint services."""

    PRINTER_CONNECT = "printer_connect"


class OctoPrintServiceArgument(StrEnum):
    """Store keys for OctoPrint service arguments."""

    PROFILE_NAME = "profile_name"
    PORT = "port"
    BAUDRATE = "baudrate"


SERVICE_CONNECT_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Optional(OctoPrintServiceArgument.PROFILE_NAME): cv.string,
        probatio.Optional(OctoPrintServiceArgument.PORT): cv.string,
        probatio.Optional(OctoPrintServiceArgument.BAUDRATE): cv.positive_int,
    }
)


def async_get_client_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> OctoprintClient:
    """Get the client related to a service call (by device ID)."""
    _, config_entry = service.async_get_device_and_config_entry(
        hass, DOMAIN, call.data[CommonServiceArgument.DEVICE_ID]
    )
    return cast(OctoprintConfigEntry, config_entry).runtime_data.octoprint


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    async def async_printer_connect(call: ServiceCall) -> None:
        """Connect to a printer."""
        client = async_get_client_for_service_call(hass, call)
        await client.connect(
            printer_profile=call.data.get(OctoPrintServiceArgument.PROFILE_NAME),
            port=call.data.get(OctoPrintServiceArgument.PORT),
            baud_rate=call.data.get(OctoPrintServiceArgument.BAUDRATE),
        )

    hass.services.async_register(
        DOMAIN,
        OctoPrintService.PRINTER_CONNECT,
        async_printer_connect,
        schema=SERVICE_CONNECT_SCHEMA,
    )
