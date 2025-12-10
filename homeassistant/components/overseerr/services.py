"""Define services for the Overseerr integration."""

from dataclasses import asdict
from typing import Any, cast

from python_overseerr import (
    IssueStatus,
    IssueType,
    OverseerrClient,
    OverseerrConnectionError,
)
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

from .const import (
    ATTR_ISSUE_ID,
    ATTR_ISSUE_STATUS,
    ATTR_ISSUE_TYPE,
    ATTR_MEDIA_ID,
    ATTR_MESSAGE,
    ATTR_PROBLEM_EPISODE,
    ATTR_PROBLEM_SEASON,
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

SERVICE_GET_ISSUES = "get_issues"
SERVICE_GET_ISSUES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Optional(ATTR_ISSUE_STATUS): vol.In(["open", "resolved"]),
        vol.Optional(ATTR_SORT_ORDER): vol.In(["added", "modified"]),
        vol.Optional(ATTR_REQUESTED_BY): int,
    }
)

SERVICE_CREATE_ISSUE = "create_issue"
SERVICE_CREATE_ISSUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_ISSUE_TYPE): vol.In([1, 2, 3, 4]),
        vol.Required(ATTR_MESSAGE): str,
        vol.Required(ATTR_MEDIA_ID): int,
        vol.Optional(ATTR_PROBLEM_SEASON, default=0): int,
        vol.Optional(ATTR_PROBLEM_EPISODE, default=0): int,
    }
)

SERVICE_UPDATE_ISSUE = "update_issue"
SERVICE_UPDATE_ISSUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_ISSUE_ID): int,
        vol.Optional(ATTR_ISSUE_STATUS): vol.In([1, 2]),
        vol.Optional(ATTR_MESSAGE): str,
    }
)

SERVICE_DELETE_ISSUE = "delete_issue"
SERVICE_DELETE_ISSUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_ISSUE_ID): int,
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


async def _async_get_issues(call: ServiceCall) -> ServiceResponse:
    """Get issues from Overseerr."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    client = entry.runtime_data.client
    kwargs: dict[str, Any] = {}
    if status := call.data.get(ATTR_ISSUE_STATUS):
        kwargs["status"] = status
    if sort_order := call.data.get(ATTR_SORT_ORDER):
        kwargs["sort"] = sort_order
    if requested_by := call.data.get(ATTR_REQUESTED_BY):
        kwargs["requested_by"] = requested_by
    try:
        issues = await client.get_issues(**kwargs)
    except OverseerrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    return {"issues": cast(list[JsonValueType], [asdict(issue) for issue in issues])}


async def _async_create_issue(call: ServiceCall) -> ServiceResponse:
    """Create a new issue in Overseerr."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    client = entry.runtime_data.client

    try:
        issue = await client.create_issue(  # type: ignore[attr-defined]
            issue_type=IssueType(call.data[ATTR_ISSUE_TYPE]),
            message=call.data[ATTR_MESSAGE],
            media_id=call.data[ATTR_MEDIA_ID],
            problem_season=call.data.get(ATTR_PROBLEM_SEASON, 0),
            problem_episode=call.data.get(ATTR_PROBLEM_EPISODE, 0),
        )
    except OverseerrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    # Trigger coordinator refresh to update sensors
    await entry.runtime_data.async_refresh()

    return {"issue": cast(dict[str, JsonValueType], asdict(issue))}


async def _async_update_issue(call: ServiceCall) -> ServiceResponse:
    """Update an existing issue in Overseerr."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    client = entry.runtime_data.client

    try:
        issue = await client.update_issue(  # type: ignore[attr-defined]
            issue_id=call.data[ATTR_ISSUE_ID],
            status=(
                IssueStatus(call.data[ATTR_ISSUE_STATUS])
                if ATTR_ISSUE_STATUS in call.data
                else None
            ),
            message=call.data.get(ATTR_MESSAGE),
        )
    except OverseerrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    # Trigger coordinator refresh to update sensors
    await entry.runtime_data.async_refresh()

    return {"issue": cast(dict[str, JsonValueType], asdict(issue))}


async def _async_delete_issue(call: ServiceCall) -> ServiceResponse:
    """Delete an issue from Overseerr."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    client = entry.runtime_data.client

    try:
        await client.delete_issue(call.data[ATTR_ISSUE_ID])  # type: ignore[attr-defined]
    except OverseerrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    # Trigger coordinator refresh to update sensors
    await entry.runtime_data.async_refresh()

    return {}


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
        SERVICE_GET_ISSUES,
        _async_get_issues,
        schema=SERVICE_GET_ISSUES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_ISSUE,
        _async_create_issue,
        schema=SERVICE_CREATE_ISSUE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_ISSUE,
        _async_update_issue,
        schema=SERVICE_UPDATE_ISSUE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_ISSUE,
        _async_delete_issue,
        schema=SERVICE_DELETE_ISSUE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
