"""Event parser and human readable log generator."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as dt
import json
from typing import Any, cast

from sqlalchemy.engine.row import Row

from homeassistant.const import ATTR_ICON, EVENT_STATE_CHANGED
from homeassistant.core import Event, State, callback


class LazyEventPartialState:
    """A lazy version of core Event with limited State joined in."""

    __slots__ = [
        "row",
        "_event_data",
        "_event_data_cache",
        "event_type",
        "entity_id",
        "state",
        "context_id",
        "context_user_id",
        "context_parent_id",
        "data",
    ]

    def __init__(
        self,
        row: Row | EventAsRow,
        event_data_cache: dict[str, dict[str, Any]],
    ) -> None:
        """Init the lazy event."""
        self.row = row
        self._event_data: dict[str, Any] | None = None
        self._event_data_cache = event_data_cache
        self.event_type: str | None = self.row.event_type
        self.entity_id: str | None = self.row.entity_id
        self.state = self.row.state
        self.context_id: str | None = self.row.context_id
        self.context_user_id: str | None = self.row.context_user_id
        self.context_parent_id: str | None = self.row.context_parent_id
        if data := getattr(row, "event_data", None):
            self.data = data
            return
        source: str = self.row.shared_data or self.row.event_data  # type: ignore[assignment]
        if not source:
            self.data = {}
        elif event_data := self._event_data_cache.get(source):
            self.data = event_data
        else:
            self.data = self._event_data_cache[source] = cast(
                dict[str, Any], json.loads(source)
            )


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
