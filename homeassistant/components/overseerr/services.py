"""Define services for the Overseerr integration."""

from dataclasses import asdict
from typing import Any, cast

from python_overseerr import OverseerrClient, OverseerrConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util.json import JsonValueType

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_REQUESTED_BY,
    ATTR_SORT_ORDER,
    ATTR_STATUS,
    DOMAIN,
    LOGGER,
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


async def get_media(
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


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Overseerr integration."""

    async def async_get_requests(call: ServiceCall) -> ServiceResponse:
        """Get requests made to Overseerr."""
        entry = async_get_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])
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
            req["media"] = await get_media(
                client, request.media.media_type, request.media.tmdb_id
            )
            result.append(req)

        return {"requests": cast(list[JsonValueType], result)}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_REQUESTS,
        async_get_requests,
        schema=SERVICE_GET_REQUESTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
