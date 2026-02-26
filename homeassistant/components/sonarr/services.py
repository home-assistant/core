"""Define services for the Sonarr integration."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, cast

from aiopyarr import exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DISKS,
    ATTR_ENTRY_ID,
    ATTR_EPISODES,
    ATTR_SHOWS,
    DEFAULT_UPCOMING_DAYS,
    DOMAIN,
    SERVICE_GET_DISKSPACE,
    SERVICE_GET_EPISODES,
    SERVICE_GET_QUEUE,
    SERVICE_GET_SERIES,
    SERVICE_GET_UPCOMING,
    SERVICE_GET_WANTED,
)
from .coordinator import SonarrConfigEntry
from .helpers import (
    format_diskspace,
    format_episodes,
    format_queue,
    format_series,
    format_upcoming,
    format_wanted,
)

# Service parameter constants
CONF_DAYS = "days"
CONF_MAX_ITEMS = "max_items"
CONF_SERIES_ID = "series_id"
CONF_SEASON_NUMBER = "season_number"
CONF_SPACE_UNIT = "space_unit"

# Valid space units
SPACE_UNITS = ["bytes", "KB", "KiB", "MB", "MiB", "GB", "GiB", "TB", "TiB", "PB", "PiB"]
DEFAULT_SPACE_UNIT = "bytes"

# Default values - 0 means no limit
DEFAULT_MAX_ITEMS = 0

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): selector.ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
    }
)

SERVICE_GET_SERIES_SCHEMA = SERVICE_BASE_SCHEMA

SERVICE_GET_EPISODES_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_SERIES_ID): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(CONF_SEASON_NUMBER): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)

SERVICE_GET_QUEUE_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_MAX_ITEMS, default=DEFAULT_MAX_ITEMS): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=500)
        ),
    }
)

SERVICE_GET_DISKSPACE_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_SPACE_UNIT, default=DEFAULT_SPACE_UNIT): vol.In(SPACE_UNITS),
    }
)

SERVICE_GET_UPCOMING_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_DAYS, default=DEFAULT_UPCOMING_DAYS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=30)
        ),
    }
)

SERVICE_GET_WANTED_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_MAX_ITEMS, default=DEFAULT_MAX_ITEMS): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=500)
        ),
    }
)


def _get_config_entry_from_service_data(call: ServiceCall) -> SonarrConfigEntry:
    """Return config entry for entry id."""
    config_entry_id: str = call.data[ATTR_ENTRY_ID]
    if not (entry := call.hass.config_entries.async_get_entry(config_entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": config_entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": entry.title},
        )
    return cast(SonarrConfigEntry, entry)


async def _handle_api_errors[_T](func: Callable[[], Awaitable[_T]]) -> _T:
    """Handle API errors and raise HomeAssistantError with user-friendly messages."""
    try:
        return await func()
    except exceptions.ArrAuthenticationException as ex:
        raise HomeAssistantError("Authentication failed for Sonarr") from ex
    except exceptions.ArrConnectionException as ex:
        raise HomeAssistantError("Failed to connect to Sonarr") from ex
    except exceptions.ArrException as ex:
        raise HomeAssistantError(f"Sonarr API error: {ex}") from ex


async def _async_get_series(service: ServiceCall) -> dict[str, Any]:
    """Get all Sonarr series."""
    entry = _get_config_entry_from_service_data(service)

    api_client = entry.runtime_data.status.api_client
    series_list = await _handle_api_errors(api_client.async_get_series)

    base_url = entry.data[CONF_URL]
    shows = format_series(cast(list, series_list), base_url)

    return {ATTR_SHOWS: shows}


async def _async_get_episodes(service: ServiceCall) -> dict[str, Any]:
    """Get episodes for a specific series."""
    entry = _get_config_entry_from_service_data(service)
    series_id: int = service.data[CONF_SERIES_ID]
    season_number: int | None = service.data.get(CONF_SEASON_NUMBER)

    api_client = entry.runtime_data.status.api_client
    episodes = await _handle_api_errors(
        lambda: api_client.async_get_episodes(series_id, series=True)
    )

    formatted_episodes = format_episodes(cast(list, episodes), season_number)

    return {ATTR_EPISODES: formatted_episodes}


async def _async_get_queue(service: ServiceCall) -> dict[str, Any]:
    """Get Sonarr queue."""
    entry = _get_config_entry_from_service_data(service)
    max_items: int = service.data[CONF_MAX_ITEMS]

    api_client = entry.runtime_data.status.api_client
    # 0 means no limit - use a large page size to get all items
    page_size = max_items if max_items > 0 else 10000
    queue = await _handle_api_errors(
        lambda: api_client.async_get_queue(
            page_size=page_size, include_series=True, include_episode=True
        )
    )

    base_url = entry.data[CONF_URL]
    shows = format_queue(queue, base_url)

    return {ATTR_SHOWS: shows}


async def _async_get_diskspace(service: ServiceCall) -> dict[str, Any]:
    """Get Sonarr diskspace information."""
    entry = _get_config_entry_from_service_data(service)
    space_unit: str = service.data[CONF_SPACE_UNIT]

    api_client = entry.runtime_data.status.api_client
    disks = await _handle_api_errors(api_client.async_get_diskspace)

    return {ATTR_DISKS: format_diskspace(disks, space_unit)}


async def _async_get_upcoming(service: ServiceCall) -> dict[str, Any]:
    """Get Sonarr upcoming episodes."""
    entry = _get_config_entry_from_service_data(service)
    days: int = service.data[CONF_DAYS]

    api_client = entry.runtime_data.status.api_client

    local = dt_util.start_of_local_day().replace(microsecond=0)
    start = dt_util.as_utc(local)
    end = start + timedelta(days=days)

    calendar = await _handle_api_errors(
        lambda: api_client.async_get_calendar(
            start_date=start, end_date=end, include_series=True
        )
    )

    base_url = entry.data[CONF_URL]
    episodes = format_upcoming(cast(list, calendar), base_url)

    return {ATTR_EPISODES: episodes}


async def _async_get_wanted(service: ServiceCall) -> dict[str, Any]:
    """Get Sonarr wanted/missing episodes."""
    entry = _get_config_entry_from_service_data(service)
    max_items: int = service.data[CONF_MAX_ITEMS]

    api_client = entry.runtime_data.status.api_client
    # 0 means no limit - use a large page size to get all items
    page_size = max_items if max_items > 0 else 10000
    wanted = await _handle_api_errors(
        lambda: api_client.async_get_wanted(page_size=page_size, include_series=True)
    )

    base_url = entry.data[CONF_URL]
    episodes = format_wanted(wanted, base_url)

    return {ATTR_EPISODES: episodes}


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
        SERVICE_GET_EPISODES,
        _async_get_episodes,
        schema=SERVICE_GET_EPISODES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_QUEUE,
        _async_get_queue,
        schema=SERVICE_GET_QUEUE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DISKSPACE,
        _async_get_diskspace,
        schema=SERVICE_GET_DISKSPACE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_UPCOMING,
        _async_get_upcoming,
        schema=SERVICE_GET_UPCOMING_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_WANTED,
        _async_get_wanted,
        schema=SERVICE_GET_WANTED_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
