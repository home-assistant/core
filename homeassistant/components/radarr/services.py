"""Define services for the Radarr integration."""

from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector

from .const import (
    ATTR_MOVIES,
    CONF_ENTRY_ID,
    DOMAIN,
    SERVICE_GET_MOVIES,
    SERVICE_GET_QUEUE,
)
from .coordinator import RadarrConfigEntry
from .helpers import format_movies, format_queue

# Service parameter constants
CONF_MAX_ITEMS = "max_items"

# Default values - 0 means no limit
DEFAULT_MAX_ITEMS = 0

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTRY_ID): selector.ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
    }
)

SERVICE_GET_MOVIES_SCHEMA = SERVICE_BASE_SCHEMA

SERVICE_GET_QUEUE_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_MAX_ITEMS, default=DEFAULT_MAX_ITEMS): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=500)
        ),
    }
)


def _get_config_entry_from_service_data(call: ServiceCall) -> RadarrConfigEntry:
    """Return config entry for entry id."""
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
    return cast(RadarrConfigEntry, entry)


async def _async_get_movies(service: ServiceCall) -> dict[str, Any]:
    """Get all Radarr movies."""
    entry = _get_config_entry_from_service_data(service)

    api_client = entry.runtime_data.status.api_client
    movies_list = await api_client.async_get_movies()

    # Get base URL from config entry for image URLs
    base_url = entry.data[CONF_URL]
    movies = format_movies(cast(list, movies_list), base_url)

    return {
        ATTR_MOVIES: movies,
    }


async def _async_get_queue(service: ServiceCall) -> dict[str, Any]:
    """Get Radarr queue."""
    entry = _get_config_entry_from_service_data(service)
    max_items: int = service.data[CONF_MAX_ITEMS]

    api_client = entry.runtime_data.status.api_client

    if max_items > 0:
        page_size = max_items
    else:
        # Get total count first, then fetch all items
        total = (await api_client.async_get_queue(page_size=1)).totalRecords
        page_size = total if total > 0 else 1

    queue = await api_client.async_get_queue(page_size=page_size, include_movie=True)

    # Get base URL from config entry for image URLs
    base_url = entry.data[CONF_URL]

    movies = format_queue(queue, base_url)

    return {
        ATTR_MOVIES: movies,
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Radarr integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_MOVIES,
        _async_get_movies,
        schema=SERVICE_GET_MOVIES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_QUEUE,
        _async_get_queue,
        schema=SERVICE_GET_QUEUE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
