"""Tests for the Home Connect integration."""

from typing import Any

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfStatus,
    Event,
    EventKey,
    EventMessage,
    EventType,
    Status,
    StatusKey,
)
from pytest_homeassistant.common import load_json_object_fixture

MOCK_PROGRAMS: dict[str, Any] = load_json_object_fixture("home_connect/programs.json")
MOCK_SETTINGS: dict[str, Any] = load_json_object_fixture("home_connect/settings.json")
MOCK_STATUS = ArrayOfStatus.from_dict(
    load_json_object_fixture("home_connect/status.json")["data"]  # type: ignore[arg-type]
)
MOCK_AVAILABLE_COMMANDS: dict[str, Any] = load_json_object_fixture(
    "home_connect/available_commands.json"
)


def create_event_message(
    ha_id: str, event_type: EventType, items: dict[EventKey, Any]
) -> EventMessage:
    """Return an event message with the given event values."""
    return EventMessage(
        ha_id,
        event_type,
        ArrayOfEvents(
            [
                Event(
                    key=event_key,
                    raw_key=event_key.value,
                    timestamp=0,
                    level="",
                    handling="",
                    value=value,
                )
                for event_key, value in items.items()
            ]
        ),
    )


def create_operation_state_status(operation_state: str) -> ArrayOfStatus:
    """Return the appliance status with the given operation state."""
    return ArrayOfStatus(
        [
            Status(
                StatusKey.BSH_COMMON_OPERATION_STATE,
                StatusKey.BSH_COMMON_OPERATION_STATE.value,
                operation_state,
            )
        ]
    )
