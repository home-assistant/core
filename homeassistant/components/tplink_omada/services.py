"""Services for the TP-Link Omada integration."""

from typing import cast

from tplink_omada_client.exceptions import OmadaClientException
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector, service

from .const import DOMAIN
from .controller import OmadaSiteController

SERVICE_RECONNECT_CLIENT = "reconnect_client"
SERVICE_RECONNECT = "reconnect"
SERVICE_BLOCK = "block"
SERVICE_UNBLOCK = "unblock"

ATTR_MAC = "mac"


def _get_controller(call: ServiceCall) -> OmadaSiteController:
    if call.data.get(ATTR_CONFIG_ENTRY_ID):
        entry = call.hass.config_entries.async_get_entry(
            call.data[ATTR_CONFIG_ENTRY_ID]
        )
        if not entry:
            raise ServiceValidationError("Specified TP-Link Omada controller not found")
    else:
        # Assume first loaded entry if none specified
        # (for backward compatibility/99% use case)
        entries = call.hass.config_entries.async_entries(DOMAIN)
        if len(entries) == 0:
            raise ServiceValidationError("No active TP-Link Omada controllers found")
        entry = entries[0]

    entry = cast(ConfigEntry[OmadaSiteController], entry)

    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            "The TP-Link Omada integration is not currently available"
        )
    return entry.runtime_data


SCHEMA_RECONNECT_CLIENT = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        vol.Required(ATTR_MAC): cv.string,
    }
)


async def _handle_reconnect_client(call: ServiceCall) -> None:
    """Handle the service action to force reconnection of a network client."""
    controller = _get_controller(call)

    mac: str = call.data[ATTR_MAC]

    try:
        await controller.omada_client.reconnect_client(mac)
    except OmadaClientException as ex:
        raise HomeAssistantError(f"Failed to reconnect client with MAC {mac}") from ex


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the TP-Link Omada integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        _handle_reconnect_client,
        schema=SCHEMA_RECONNECT_CLIENT,
    )
    for service_name, func, admin_only in (
        (SERVICE_RECONNECT, "async_reconnect", False),
        (SERVICE_BLOCK, "async_block", True),
        (SERVICE_UNBLOCK, "async_unblock", True),
    ):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            service_name,
            entity_domain=DEVICE_TRACKER_DOMAIN,
            schema=vol.Schema({}),
            func=func,
            admin_only=admin_only,
        )
