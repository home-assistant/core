"""Ohme services."""

from typing import Final

from ohme import OhmeApiClient
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import selector, service

from .const import DOMAIN
from .coordinator import OhmeConfigEntry

ATTR_CONFIG_ENTRY: Final = "config_entry"
ATTR_PRICE_CAP: Final = "price_cap"

SERVICE_LIST_CHARGE_SLOTS = "list_charge_slots"
SERVICE_LIST_CHARGE_SLOTS_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
    }
)

SERVICE_SET_PRICE_CAP = "set_price_cap"
SERVICE_SET_PRICE_CAP_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        vol.Required(ATTR_PRICE_CAP): vol.Coerce(float),
    }
)


def __get_client(call: ServiceCall) -> OhmeApiClient:
    """Get the client from the config entry."""
    entry: OhmeConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY]
    )

    return entry.runtime_data.charge_session_coordinator.client


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    async def list_charge_slots(
        service_call: ServiceCall,
    ) -> ServiceResponse:
        """List of charge slots."""
        client = __get_client(service_call)

        return {"slots": [slot.to_dict() for slot in client.slots]}

    async def set_price_cap(
        service_call: ServiceCall,
    ) -> None:
        """List of charge slots."""
        client = __get_client(service_call)
        price_cap = service_call.data[ATTR_PRICE_CAP]
        await client.async_change_price_cap(cap=price_cap)

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_CHARGE_SLOTS,
        list_charge_slots,
        schema=SERVICE_LIST_CHARGE_SLOTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PRICE_CAP,
        set_price_cap,
        schema=SERVICE_SET_PRICE_CAP_SCHEMA,
        supports_response=SupportsResponse.NONE,
    )
