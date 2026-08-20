"""Services for the TP-Link Omada integration."""

from typing import Literal, cast

from tplink_omada_client.exceptions import OmadaClientException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN
from .controller import OmadaSiteController

SERVICE_RECONNECT_CLIENT = "reconnect_client"
SERVICE_RECONNECT = "reconnect"
SERVICE_BLOCK = "block"
SERVICE_UNBLOCK = "unblock"

ATTR_MAC = "mac"

SERVICE_ACTIONS: dict[str, Literal["reconnect", "block", "unblock"]] = {
    SERVICE_RECONNECT_CLIENT: "reconnect",
    SERVICE_RECONNECT: "reconnect",
    SERVICE_BLOCK: "block",
    SERVICE_UNBLOCK: "unblock",
}


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


async def _handle_client_action(call: ServiceCall) -> None:
    """Handle a service action for a network client."""
    controller = _get_controller(call)
    mac: str = call.data[ATTR_MAC]
    action = SERVICE_ACTIONS[call.service]

    try:
        if action == "reconnect":
            await controller.omada_client.reconnect_client(mac)
        elif action == "block":
            await controller.omada_client.block_client(mac)
        else:
            await controller.omada_client.unblock_client(mac)
    except OmadaClientException as ex:
        raise HomeAssistantError(f"Failed to {action} client with MAC {mac}") from ex


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the TP-Link Omada integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECONNECT_CLIENT,
        _handle_client_action,
        schema=SCHEMA_RECONNECT_CLIENT,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECONNECT,
        _handle_client_action,
        schema=SCHEMA_RECONNECT_CLIENT,
    )
    for service in (SERVICE_BLOCK, SERVICE_UNBLOCK):
        async_register_admin_service(
            hass,
            DOMAIN,
            service,
            _handle_client_action,
            schema=SCHEMA_RECONNECT_CLIENT,
        )
