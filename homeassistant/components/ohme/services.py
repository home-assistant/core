"""Ohme services."""

from .const import DOMAIN
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
    ServiceResponse,
)
import voluptuous as vol
from typing import Final
from homeassistant.helpers import selector
from homeassistant.exceptions import ServiceValidationError
from .const import DOMAIN
from homeassistant.config_entries import ConfigEntry

from ohme import OhmeApiClient
from homeassistant.config_entries import ConfigEntryState

SERVICE_LIST_CHARGE_SLOTS = "list_charge_slots"
SERVICES = [
    SERVICE_LIST_CHARGE_SLOTS,
]
ATTR_CONFIG_ENTRY: Final = "config_entry"
SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
    }
)


def __get_client(call: ServiceCall) -> OhmeApiClient:
    """Get the client from the config entry."""
    entry_id: str = call.data[ATTR_CONFIG_ENTRY]
    entry: ConfigEntry | None = call.hass.config_entries.async_get_entry(entry_id)

    if not entry:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_config_entry",
            translation_placeholders={
                "config_entry": entry_id,
            },
        )
    if entry.state != ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unloaded_config_entry",
            translation_placeholders={
                "config_entry": entry.title,
            },
        )

    return entry.runtime_data.charge_session_coordinator.client


def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    async def list_charge_slots(service_call: ServiceCall) -> None:
        """List of charge slots."""
        client = __get_client(service_call)

        return {"slots": client.slots}

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_CHARGE_SLOTS,
        list_charge_slots,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
