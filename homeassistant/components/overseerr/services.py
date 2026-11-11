"""Define services for the Overseerr integration."""

import ast
from dataclasses import asdict
from enum import StrEnum
from typing import Any, Literal, cast

import probatio
from python_overseerr import OverseerrClient, OverseerrConnectionError

from homeassistant.const import CommonServiceArgument
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import service
from homeassistant.util.json import JsonValueType

from .const import DOMAIN, LOGGER
from .coordinator import OverseerrConfigEntry


class OverseerrService(StrEnum):
    """Store keys for Overseerr services."""

    GET_REQUESTS = "get_requests"
    REQUEST_MEDIA = "request_media"
    SEARCH_MEDIA = "search_media"


class OverseerrServiceArgument(StrEnum):
    """Store keys for Overseerr service arguments."""

    MEDIA_ID = "media_id"
    MEDIA_TYPE = "media_type"
    QUERY = "query"
    REQUESTED_BY = "requested_by"
    SEASONS = "seasons"
    SORT_ORDER = "sort_order"
    STATUS = "status"


SERVICE_GET_REQUESTS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): str,
        probatio.Optional(OverseerrServiceArgument.STATUS): probatio.In(
            ["approved", "pending", "available", "processing", "unavailable", "failed"]
        ),
        probatio.Optional(OverseerrServiceArgument.SORT_ORDER): probatio.In(
            ["added", "modified"]
        ),
        probatio.Optional(OverseerrServiceArgument.REQUESTED_BY): int,
    }
)

SERVICE_SEARCH_MEDIA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): str,
        probatio.Required(OverseerrServiceArgument.QUERY): str,
    }
)

SERVICE_REQUEST_MEDIA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): str,
        probatio.Required(OverseerrServiceArgument.MEDIA_TYPE): probatio.In(
            ["movie", "tv"]
        ),
        probatio.Required(OverseerrServiceArgument.MEDIA_ID): probatio.All(
            probatio.Coerce(int),
            probatio.Range(min=1),
        ),
        probatio.Optional(OverseerrServiceArgument.SEASONS): probatio.Any(
            probatio.Coerce(int),
            [probatio.Coerce(int)],
            str,
        ),
    }
)


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
    """Get requests made to Seerr."""
    entry: OverseerrConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )
    client = entry.runtime_data.client
    kwargs: dict[str, Any] = {}
    if status := call.data.get(OverseerrServiceArgument.STATUS):
        kwargs["status"] = status
    if sort_order := call.data.get(OverseerrServiceArgument.SORT_ORDER):
        kwargs["sort"] = sort_order
    if requested_by := call.data.get(OverseerrServiceArgument.REQUESTED_BY):
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
        for user in (req["modified_by"], req["requested_by"]):
            del user["avatar_e_tag"]
            del user["avatar_version"]
            del user["permissions"]
            del user["recovery_link_expiration_date"]
            del user["settings"]
            del user["user_type"]
            del user["warnings"]
        result.append(req)

    return {"requests": cast(list[JsonValueType], result)}


async def _async_search_media(call: ServiceCall) -> ServiceResponse:
    """Search for media in Seerr."""
    entry: OverseerrConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )
    client = entry.runtime_data.client
    query = call.data[OverseerrServiceArgument.QUERY]

    LOGGER.debug("Searching for '%s'", query)
    try:
        search_results = await client.search(query)
    except OverseerrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    return {
        "results": cast(
            list[JsonValueType], [asdict(result) for result in search_results]
        )
    }


async def _async_request_media(call: ServiceCall) -> ServiceResponse:
    """Request media in Seerr."""
    entry: OverseerrConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )
    client = entry.runtime_data.client
    media_type = call.data[OverseerrServiceArgument.MEDIA_TYPE]
    media_id = call.data[OverseerrServiceArgument.MEDIA_ID]
    seasons = parse_seasons_input(call.data.get(OverseerrServiceArgument.SEASONS))

    LOGGER.debug(
        "Requesting %s with media ID %s (seasons: %s)",
        media_type,
        media_id,
        seasons or "none",
    )
    try:
        # We can always pass in the seasons, they will be ignored if the media type isn't TV
        request = await client.create_request(media_type, media_id, seasons)
    except OverseerrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    return {"request": cast(JsonValueType, asdict(request))}


def parse_seasons_input(seasons_input: Any | None) -> Literal["all"] | list[int]:
    """Parse all possible inputs to "all" or a list of integers."""
    seasons_str = str(seasons_input).strip()
    if seasons_input is None or seasons_str in ("", "all"):
        return "all"

    try:
        parsed = ast.literal_eval(seasons_str)
        if isinstance(parsed, int):
            return [parsed]
        return [int(season) for season in parsed]
    except ValueError, SyntaxError, TypeError:
        LOGGER.error("Unable to cast input to a list '%s'", seasons_input)
        return "all"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Seerr integration."""

    hass.services.async_register(
        DOMAIN,
        OverseerrService.GET_REQUESTS,
        _async_get_requests,
        schema=SERVICE_GET_REQUESTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        OverseerrService.SEARCH_MEDIA,
        _async_search_media,
        schema=SERVICE_SEARCH_MEDIA_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        OverseerrService.REQUEST_MEDIA,
        _async_request_media,
        schema=SERVICE_REQUEST_MEDIA_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
