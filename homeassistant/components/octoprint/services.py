"""Services for octoprint."""

from typing import cast

from pyoctoprintapi import OctoprintClient
import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_PORT, CONF_PROFILE_NAME
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .const import CONF_BAUDRATE, DOMAIN, SERVICE_CONNECT
from .coordinator import OctoprintConfigEntry

SERVICE_CONNECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Optional(CONF_PROFILE_NAME): cv.string,
        vol.Optional(CONF_PORT): cv.string,
        vol.Optional(CONF_BAUDRATE): cv.positive_int,
    }
)


def async_get_client_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> OctoprintClient:
    """Get the client related to a service call (by device ID)."""
    _, config_entry = service.async_get_device_and_config_entry(
        hass, DOMAIN, call.data[CONF_DEVICE_ID]
    )
    return cast(OctoprintConfigEntry, config_entry).runtime_data.octoprint


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    async def async_printer_connect(call: ServiceCall) -> None:
        """Connect to a printer."""
        client = async_get_client_for_service_call(hass, call)
        await client.connect(
            printer_profile=call.data.get(CONF_PROFILE_NAME),
            port=call.data.get(CONF_PORT),
            baud_rate=call.data.get(CONF_BAUDRATE),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CONNECT,
        async_printer_connect,
        schema=SERVICE_CONNECT_SCHEMA,
    )
