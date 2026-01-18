"""Define services for the Sonarr integration."""

from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector

from .const import (
    ATTR_SHOWS,
    CONF_ENTRY_ID,
    DEFAULT_MAX_RECORDS,
    DOMAIN,
    SERVICE_GET_QUEUE,
    SERVICE_GET_SERIES,
)
from .coordinator import SonarrConfigEntry
from .helpers import format_queue, format_series

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTRY_ID): selector.ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
    }
)

SERVICE_GET_SERIES_SCHEMA = SERVICE_BASE_SCHEMA
SERVICE_GET_QUEUE_SCHEMA = SERVICE_BASE_SCHEMA


def _get_config_entry_from_service_data(call: ServiceCall) -> SonarrConfigEntry:
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
    return cast(SonarrConfigEntry, entry)


async def _async_get_series(service: ServiceCall) -> dict[str, Any]:
    """Get all Sonarr series."""
    entry = _get_config_entry_from_service_data(service)

    # Get the API client from runtime_data
    api_client = entry.runtime_data.status.api_client

    # Fetch series from the API
    series_list = await api_client.async_get_series()

    # Get base URL from config entry for image URLs
    base_url = entry.data[CONF_URL]

    # Format the data for return
    shows = format_series(cast(list, series_list), base_url)

    return {
        ATTR_SHOWS: shows,
    }


async def _async_get_queue(service: ServiceCall) -> dict[str, Any]:
    """Get Sonarr queue."""
    entry = _get_config_entry_from_service_data(service)

    # Get the API client from runtime_data
    api_client = entry.runtime_data.status.api_client

    # Fetch queue data from the API
    queue = await api_client.async_get_queue(
        page_size=DEFAULT_MAX_RECORDS, include_series=True
    )

    # Get base URL from config entry for image URLs
    base_url = entry.data[CONF_URL]

    # Format the data for return
    shows = format_queue(queue, base_url)

    return {
        ATTR_SHOWS: shows,
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Sonarr integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SERIES,
        _async_get_series,
        schema=SERVICE_GET_SERIES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_QUEUE,
        _async_get_queue,
        schema=SERVICE_GET_QUEUE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
