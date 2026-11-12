"""Actions for the Broadlink integration."""

from enum import StrEnum

from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import DOMAIN


class BroadlinkService(StrEnum):
    """Names of the Broadlink actions."""

    LIST_COMMANDS = "list_commands"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Broadlink actions."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BroadlinkService.LIST_COMMANDS,
        entity_domain=REMOTE_DOMAIN,
        schema=None,
        func="async_list_commands",
        supports_response=SupportsResponse.ONLY,
    )
