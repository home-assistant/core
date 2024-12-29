"""Define services for the Overseerr integration."""

from dataclasses import asdict
from typing import cast

from aiomealie import MealieConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_REQUESTED_BY,
    ATTR_SORT_ORDER,
    ATTR_STATUS,
    DOMAIN,
)
from .coordinator import OverseerrConfigEntry

SERVICE_GET_REQUESTS = "get_requests"
SERVICE_GET_REQUESTS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Optional(ATTR_STATUS): vol.In(
            ["approved", "pending", "available", "processing", "unavailable", "failed"]
        ),
        vol.Optional(ATTR_SORT_ORDER): vol.In(["added", "modified"]),
        vol.Optional(ATTR_REQUESTED_BY): int,
    }
)


def async_get_entry(hass: HomeAssistant, config_entry_id: str) -> OverseerrConfigEntry:
    """Get the Overseerr config entry."""
    if not (entry := hass.config_entries.async_get_entry(config_entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": DOMAIN},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": entry.title},
        )
    return cast(OverseerrConfigEntry, entry)


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Overseerr integration."""

    async def async_get_requests(call: ServiceCall) -> ServiceResponse:
        """Get requests made to Overseerr."""
        entry = async_get_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        client = entry.runtime_data.client
        try:
            requests = await client.get_requests()
        except MealieConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err
        return {"requests": [asdict(x) for x in requests]}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_REQUESTS,
        async_get_requests,
        schema=SERVICE_GET_REQUESTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
