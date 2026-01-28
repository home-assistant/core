"""Define services for the Overseerr integration."""

from dataclasses import asdict
from typing import Any, cast

from python_overseerr import (
    IssueFilterStatus,
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
    ATTR_ISSUE_TYPE,
    ATTR_MEDIA_ID,
    ATTR_MESSAGE,
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
        vol.Optional(ATTR_STATUS): vol.In(["all", "open", "resolved"]),
    }
)

SERVICE_CREATE_ISSUE = "create_issue"
SERVICE_CREATE_ISSUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_ISSUE_TYPE): vol.In(["video", "audio", "subtitle", "other"]),
        vol.Required(ATTR_MESSAGE): str,
        vol.Required(ATTR_MEDIA_ID): int,
    }
)

SERVICE_UPDATE_ISSUE = "update_issue"
SERVICE_UPDATE_ISSUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_ISSUE_ID): int,
        vol.Optional(ATTR_STATUS): vol.In(["open", "resolved"]),
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

# Mapping of string values to library enums
ISSUE_TYPE_MAP = {
    "video": IssueType.VIDEO,
    "audio": IssueType.AUDIO,
    "subtitle": IssueType.SUBTITLE,
    "other": IssueType.OTHER,
}

ISSUE_STATUS_MAP = {
    "open": IssueStatus.OPEN,
    "resolved": IssueStatus.RESOLVED,
}

ISSUE_FILTER_STATUS_MAP = {
    "all": IssueFilterStatus.ALL,
    "open": IssueFilterStatus.OPEN,
    "resolved": IssueFilterStatus.RESOLVED,
}


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
        elif media_type == "tv":
            media = asdict(await client.get_tv_details(identifier))
    except OverseerrConnectionError:
        LOGGER.error("Could not find data for %s %s", media_type, identifier)
        return {}
    if media and "media_info" in media:
        media["media_info"].pop("requests", None)
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
        if request.media.tmdb_id:
            req["media"] = await _get_media(
                client, request.media.media_type, request.media.tmdb_id
            )
        else:
            req["media"] = {}
        result.append(req)

    return {"requests": cast(list[JsonValueType], result)}


async def _async_get_issues(call: ServiceCall) -> ServiceResponse:
    """Get issues from Overseerr."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    client = entry.runtime_data.client

    status_filter = None
    if status_str := call.data.get(ATTR_STATUS):
        status_filter = ISSUE_FILTER_STATUS_MAP[status_str]

    try:
        issues = await client.get_issues(status=status_filter)
    except OverseerrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    result: list[dict[str, Any]] = []
    for issue in issues:
        issue_dict = asdict(issue)
        result.append(issue_dict)

    return {"issues": cast(list[JsonValueType], result)}


async def _async_create_issue(call: ServiceCall) -> ServiceResponse:
    """Create a new issue in Overseerr."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    client = entry.runtime_data.client

    issue_type = ISSUE_TYPE_MAP[call.data[ATTR_ISSUE_TYPE]]
    message = call.data[ATTR_MESSAGE]
    media_id = call.data[ATTR_MEDIA_ID]

    try:
        issue = await client.create_issue(
            issue_type=issue_type,
            message=message,
            media_id=media_id,
        )
    except OverseerrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    # Refresh coordinator to update issue sensors
    await entry.runtime_data.async_refresh()

    return {"issue": cast(dict[str, JsonValueType], asdict(issue))}


async def _async_update_issue(call: ServiceCall) -> ServiceResponse:
    """Update an existing issue in Overseerr."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    client = entry.runtime_data.client

    issue_id = call.data[ATTR_ISSUE_ID]
    status = None
    if status_str := call.data.get(ATTR_STATUS):
        status = ISSUE_STATUS_MAP[status_str]
    message = call.data.get(ATTR_MESSAGE)

    try:
        issue = await client.update_issue(
            issue_id=issue_id,
            status=status,
            message=message,
        )
    except OverseerrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    # Refresh coordinator to update issue sensors
    await entry.runtime_data.async_refresh()

    return {"issue": cast(dict[str, JsonValueType], asdict(issue))}


async def _async_delete_issue(call: ServiceCall) -> None:
    """Delete an issue from Overseerr."""
    entry = _async_get_entry(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    client = entry.runtime_data.client

    issue_id = call.data[ATTR_ISSUE_ID]

    try:
        await client.delete_issue(issue_id=issue_id)
    except OverseerrConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        ) from err

    # Refresh coordinator to update issue sensors
    await entry.runtime_data.async_refresh()


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
        supports_response=SupportsResponse.NONE,
    )
