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
from homeassistant.helpers.area_registry import EVENT_AREA_REGISTRY_UPDATED
from homeassistant.helpers.category_registry import EVENT_CATEGORY_REGISTRY_UPDATED
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.helpers.floor_registry import EVENT_FLOOR_REGISTRY_UPDATED
from homeassistant.helpers.issue_registry import EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED
from homeassistant.helpers.label_registry import EVENT_LABEL_REGISTRY_UPDATED
from homeassistant.util.event_type import EventType

# These are events that do not contain any sensitive data
# Except for state_changed, which is handled accordingly.
SUBSCRIBE_ALLOWLIST: Final[set[EventType[Any] | str]] = {
    EVENT_AREA_REGISTRY_UPDATED,
    EVENT_COMPONENT_LOADED,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_DEVICE_REGISTRY_UPDATED,
    EVENT_ENTITY_REGISTRY_UPDATED,
    EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
    EVENT_LOVELACE_UPDATED,
    EVENT_PANELS_UPDATED,
    EVENT_RECORDER_5MIN_STATISTICS_GENERATED,
    EVENT_RECORDER_HOURLY_STATISTICS_GENERATED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_SHOPPING_LIST_UPDATED,
    EVENT_STATE_CHANGED,
    EVENT_THEMES_UPDATED,
    EVENT_LABEL_REGISTRY_UPDATED,
    EVENT_CATEGORY_REGISTRY_UPDATED,
    EVENT_FLOOR_REGISTRY_UPDATED,
}
