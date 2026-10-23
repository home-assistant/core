"""Event parser and human readable log generator."""

from collections.abc import Callable
from typing import Any

import probatio

from homeassistant.components import frontend
from homeassistant.components.recorder import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.filters import (
    extract_include_exclude_filter_conf,
    merge_include_exclude_filters,
    sqlalchemy_filter_from_include_exclude_conf,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    convert_include_exclude_filter,
)
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.event_type import EventType

from . import rest_api, websocket_api
from .const import (  # noqa: F401
    ATTR_MESSAGE,
    DOMAIN,
    LOGBOOK_ENTRY_CONTEXT_ID,
    LOGBOOK_ENTRY_DOMAIN,
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_ICON,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LOGBOOK_ENTRY_SOURCE,
)
from .helpers import async_log_entry, log_entry  # noqa: F401
from .models import LazyEventPartialState, LogbookConfig
from .services import async_setup_services

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA}, extra=probatio.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Logbook setup."""

    frontend.async_register_built_in_panel(
        hass, "logbook", "logbook", "mdi:format-list-bulleted-type"
    )

    recorder_conf = config.get(RECORDER_DOMAIN, {})
    logbook_conf = config.get(DOMAIN, {})
    recorder_filter = extract_include_exclude_filter_conf(recorder_conf)
    logbook_filter = extract_include_exclude_filter_conf(logbook_conf)
    merged_filter = merge_include_exclude_filters(recorder_filter, logbook_filter)

    possible_merged_entities_filter = convert_include_exclude_filter(merged_filter)
    if not possible_merged_entities_filter.empty_filter:
        filters = sqlalchemy_filter_from_include_exclude_conf(merged_filter)
        entities_filter = possible_merged_entities_filter.get_filter()
    else:
        filters = None
        entities_filter = None

    external_events: dict[
        EventType[Any] | str,
        tuple[str, Callable[[LazyEventPartialState], dict[str, Any]]],
    ] = {}
    hass.data[DOMAIN] = LogbookConfig(external_events, filters, entities_filter)
    websocket_api.async_setup(hass)
    rest_api.async_setup(hass, config, filters, entities_filter)
    async_setup_services(hass)

    await async_process_integration_platforms(hass, DOMAIN, _process_logbook_platform)

    return True


@callback
def _process_logbook_platform(hass: HomeAssistant, domain: str, platform: Any) -> None:
    """Process a logbook platform."""
    logbook_config: LogbookConfig = hass.data[DOMAIN]
    external_events = logbook_config.external_events

    @callback
    def _async_describe_event(
        domain: str,
        event_name: str,
        describe_callback: Callable[[LazyEventPartialState], dict[str, Any]],
    ) -> None:
        """Teach logbook how to describe a new event."""
        external_events[event_name] = (domain, describe_callback)

    platform.async_describe_events(hass, _async_describe_event)
