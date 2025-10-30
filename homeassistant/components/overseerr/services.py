"""Define services for the Overseerr integration."""

from dataclasses import asdict
from typing import Any, cast
from urllib.parse import quote

from python_overseerr import OverseerrClient, OverseerrConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util.json import JsonValueType

from .const import ATTR_REQUESTED_BY, ATTR_SORT_ORDER, ATTR_STATUS, DOMAIN, LOGGER
from .coordinator import OverseerrConfigEntry

ATTR_QUERY = "query"
ATTR_LIMIT = "limit"
ATTR_MEDIA_TYPE = "media_type"
ATTR_TMDB_ID = "tmdb_id"
ATTR_SEASONS = "seasons"

SERVICE_GET_REQUESTS = "get_requests"
SERVICE_SEARCH_MEDIA = "search_media"
SERVICE_REQUEST_MEDIA = "request_media"

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

SERVICE_SEARCH_MEDIA_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_QUERY): str,
        vol.Optional(ATTR_LIMIT): vol.Coerce(int),
    }
)

SERVICE_REQUEST_MEDIA_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_MEDIA_TYPE): vol.In(["movie", "tv"]),
        vol.Required(ATTR_TMDB_ID): vol.Coerce(int),
        vol.Optional(ATTR_SEASONS): vol.Any(
            vol.Coerce(int),
            [vol.Coerce(int)],
            "all",
        ),
    }
)


def _async_get_entry(hass: HomeAssistant, config_entry_id: str) -> OverseerrConfigEntry:
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


async def _get_media(
    client: OverseerrClient, media_type: str, identifier: int
) -> dict[str, Any]:
    """Get media details."""
    media = {}
    try:
        if media_type == "movie":
            media = asdict(await client.get_movie_details(identifier))
        if media_type == "tv":
            media = asdict(await client.get_tv_details(identifier))
    except OverseerrConnectionError:
        LOGGER.error("Could not find data for %s %s", media_type, identifier)
        return {}
    media["media_info"].pop("requests")
    return media


async def _async_get_requests(call: ServiceCall) -> ServiceResponse:
    """Get requests made to Overseerr."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    client = entry.runtime_data.client
    kwargs: dict[str, Any] = {}
    if status := call.data.get(ATTR_STATUS):
        kwargs["status"] = status
    if sort_order := call.data.get(ATTR_SORT_ORDER):
        kwargs["sort"] = sort_order
    if requested_by := call.data.get(ATTR_REQUESTED_BY):
        kwargs["requested_by"] = requested_by
    try:
        requests = await client.get_requests(**kwargs)
    except OverseerrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err
    result: list[dict[str, Any]] = []
    for request in requests:
        req = asdict(request)
        assert request.media.tmdb_id
        req["media"] = await _get_media(
            client, request.media.media_type, request.media.tmdb_id
        )
        result.append(req)

    return {"requests": cast(list[JsonValueType], result)}


async def _async_search_media(call: ServiceCall) -> ServiceResponse:
    """Search for media in Overseerr."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    client = entry.runtime_data.client
    query = call.data[ATTR_QUERY]
    limit = call.data.get(ATTR_LIMIT)
    try:
        LOGGER.debug("Searching for '%s'", query)
        # URL encode the query to handle spaces and special characters
        search_results = await client.search(quote(query))
    except OverseerrConnectionError as err:
        LOGGER.error("Error searching for '%s': %s", query, str(err))
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    if limit is not None and limit > 0:
        search_results = search_results[:limit]

    return {"results": cast(list[JsonValueType], [asdict(result) for result in search_results])}


async def _async_request_media(call: ServiceCall) -> ServiceResponse:
    """Request media in Overseerr."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    client = entry.runtime_data.client
    media_type = call.data[ATTR_MEDIA_TYPE]
    tmdb_id = call.data[ATTR_TMDB_ID]
    seasons = call.data.get(ATTR_SEASONS)

    # Convert single integer to list for seasons
    if isinstance(seasons, int):
        seasons = [seasons]

    try:
        LOGGER.debug(
            "Requesting %s with TMDB ID %s (seasons: %s)",
            media_type,
            tmdb_id,
            seasons if seasons else "none",
        )
        request = await client.create_request(media_type, tmdb_id, seasons)
    except OverseerrConnectionError as err:
        LOGGER.error(
            "Error requesting %s with TMDB ID %s: %s",
            media_type,
            tmdb_id,
            str(err),
        )
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    return {"request": cast(JsonValueType, asdict(request))}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Overseerr integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_REQUESTS,
        _async_get_requests,
        schema=SERVICE_GET_REQUESTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_MEDIA,
        _async_search_media,
        schema=SERVICE_SEARCH_MEDIA_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_MEDIA,
        _async_request_media,
        schema=SERVICE_REQUEST_MEDIA_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
