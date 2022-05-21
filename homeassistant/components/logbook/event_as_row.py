"""Event parser and human readable log generator."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Any

from homeassistant.const import ATTR_ICON, EVENT_STATE_CHANGED
from homeassistant.core import Event, State, callback


@dataclass
class EventAsRow:
    """Convert an event to a row."""

    event_data: dict[str, Any]
    context_id: str
    time_fired: dt
    event_id: int
    old_format_icon: None = None
    state_id: None = None
    entity_id: str | None = None
    icon: str | None = None
    context_user_id: str | None = None
    context_parent_id: str | None = None
    event_type: str | None = None
    state: str | None = None
    shared_data: str | None = None
    context_only: None = None


@callback
def async_event_to_row(event: Event) -> EventAsRow | None:
    """Convert an event to a row."""
    if event.event_type != EVENT_STATE_CHANGED:
        return EventAsRow(
            event_data=event.data,
            event_type=event.event_type,
            context_id=event.context.id,
            context_user_id=event.context.user_id,
            context_parent_id=event.context.parent_id,
            time_fired=event.time_fired,
            event_id=hash(event),
        )
    if event.data.get("old_state") is None or event.data.get("new_state") is None:
        return None
    new_state: State = event.data["new_state"]
    return EventAsRow(
        event_data=event.data,
        entity_id=new_state.entity_id,
        state=new_state.state,
        context_id=new_state.context.id,
        context_user_id=new_state.context.user_id,
        context_parent_id=new_state.context.parent_id,
        time_fired=new_state.last_updated,
        event_id=hash(event),
        icon=new_state.attributes.get(ATTR_ICON),
    )
