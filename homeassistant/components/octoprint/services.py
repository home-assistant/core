"""Services for octoprint."""

from typing import cast

from pyoctoprintapi import OctoprintClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_PORT, CONF_PROFILE_NAME
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

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
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(hass)

    if device_entry := device_registry.async_get(device_id):
        for entry_id in device_entry.config_entries:
            if entry := hass.config_entries.async_get_entry(entry_id):
                if entry.domain == DOMAIN and entry.state is ConfigEntryState.LOADED:
                    return cast(OctoprintConfigEntry, entry).runtime_data.octoprint

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="missing_client",
        translation_placeholders={
            "device_id": device_id,
        },
    )


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
