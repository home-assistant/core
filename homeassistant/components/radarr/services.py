"""Define services for the Radarr integration."""

from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector

from .const import ATTR_MOVIES, CONF_ENTRY_ID, DOMAIN, SERVICE_GET_QUEUE
from .coordinator import QueueDataUpdateCoordinator
from .helpers import format_queue

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTRY_ID): selector.ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
    }
)

SERVICE_GET_QUEUE_SCHEMA = SERVICE_BASE_SCHEMA


def _get_queue_coordinator_from_service_data(
    call: ServiceCall,
) -> QueueDataUpdateCoordinator:
    """Return queue coordinator for entry id."""
    config_entry_id: str = call.data[CONF_ENTRY_ID]
    if not (entry := call.hass.config_entries.async_get_entry(config_entry_id)):
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
    # Get the queue coordinator from runtime_data
    return cast(QueueDataUpdateCoordinator, entry.runtime_data.queue)


async def _async_get_queue(service: ServiceCall) -> dict[str, Any]:
    """Get Radarr queue."""
    config_entry_id: str = service.data[CONF_ENTRY_ID]
    entry = service.hass.config_entries.async_get_entry(config_entry_id)
    coordinator = _get_queue_coordinator_from_service_data(service)

    # Get queue data from coordinator (already cached!)
    queue = coordinator.data

    # Get base URL from config entry for poster URLs
    base_url = entry.data[CONF_URL] if entry else None

    # Format the data for return
    movies = format_queue(queue, base_url)

    return {
        ATTR_MOVIES: movies,
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Radarr integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_QUEUE,
        _async_get_queue,
        schema=SERVICE_GET_QUEUE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
