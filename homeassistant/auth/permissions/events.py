"""Permission for events."""

from __future__ import annotations

from typing import Any, Final

from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_LOVELACE_UPDATED,
    EVENT_PANELS_UPDATED,
    EVENT_RECORDER_5MIN_STATISTICS_GENERATED,
    EVENT_RECORDER_HOURLY_STATISTICS_GENERATED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_SHOPPING_LIST_UPDATED,
    EVENT_STATE_CHANGED,
    EVENT_THEMES_UPDATED,
)
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util.event_type import EventType

# These are events that do not contain any sensitive data
# Except for state_changed, which is handled accordingly.
SUBSCRIBE_ALLOWLIST: Final[set[EventType[Any] | str]] = {
    ar.EVENT_AREA_REGISTRY_UPDATED,
    EVENT_COMPONENT_LOADED,
    EVENT_CORE_CONFIG_UPDATE,
    dr.EVENT_DEVICE_REGISTRY_UPDATED,
    er.EVENT_ENTITY_REGISTRY_UPDATED,
    ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
    EVENT_LOVELACE_UPDATED,
    EVENT_PANELS_UPDATED,
    EVENT_RECORDER_5MIN_STATISTICS_GENERATED,
    EVENT_RECORDER_HOURLY_STATISTICS_GENERATED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_SHOPPING_LIST_UPDATED,
    EVENT_STATE_CHANGED,
    EVENT_THEMES_UPDATED,
}
