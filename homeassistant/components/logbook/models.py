"""Event parser and human readable log generator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy.engine.row import Row

from homeassistant.components.recorder.models import (
    bytes_to_ulid_or_none,
    ulid_to_bytes_or_none,
)
from homeassistant.const import ATTR_ICON, EVENT_STATE_CHANGED
from homeassistant.core import Context, Event, State, callback
import homeassistant.util.dt as dt_util
from homeassistant.util.json import json_loads
from homeassistant.util.ulid import ulid_to_bytes


class LazyEventPartialState:
    """A lazy version of core Event with limited State joined in."""

    __slots__ = [
        "row",
        "_event_data",
        "_event_data_cache",
        "event_type",
        "entity_id",
        "state",
        "context_id_bin",
        "context_user_id",
        "context_parent_id_bin",
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
        self.context_id_bin: bytes | None = self.row.context_id_bin
        self.context_user_id: str | None = self.row.context_user_id
        self.context_parent_id_bin: bytes | None = self.row.context_parent_id_bin
        if data := getattr(row, "data", None):
            # If its an EventAsRow we can avoid the whole
            # json decode process as we already have the data
            self.data = data
            return
        source = cast(str, self.row.shared_data or self.row.event_data)
        if not source:
            self.data = {}
        elif event_data := self._event_data_cache.get(source):
            self.data = event_data
        else:
            self.data = self._event_data_cache[source] = cast(
                dict[str, Any], json_loads(source)
            )

    @property
    def context_id(self) -> str | None:
        """Return the context id."""
        return bytes_to_ulid_or_none(self.context_id_bin)

    @property
    def context_parent_id(self) -> str | None:
        """Return the context parent id."""
        return bytes_to_ulid_or_none(self.context_parent_id_bin)


@dataclass(frozen=True)
class EventAsRow:
    """Convert an event to a row."""

    data: dict[str, Any]
    context: Context
    context_id_bin: bytes
    time_fired_ts: float
    state_id: int
    event_data: str | None = None
    old_format_icon: None = None
    event_id: None = None
    entity_id: str | None = None
    icon: str | None = None
    context_user_id: str | None = None
    context_parent_id_bin: bytes | None = None
    event_type: str | None = None
    state: str | None = None
    shared_data: str | None = None
    context_only: None = None


@callback
def async_event_to_row(event: Event) -> EventAsRow:
    """Convert an event to a row."""
    if event.event_type != EVENT_STATE_CHANGED:
        return EventAsRow(
            data=event.data,
            context=event.context,
            event_type=event.event_type,
            context_id_bin=ulid_to_bytes(event.context.id),
            context_user_id=event.context.user_id,
            context_parent_id_bin=ulid_to_bytes_or_none(event.context.parent_id),
            time_fired_ts=dt_util.utc_to_timestamp(event.time_fired),
            state_id=hash(event),
        )
    # States are prefiltered so we never get states
    # that are missing new_state or old_state
    # since the logbook does not show these
    new_state: State = event.data["new_state"]
    return EventAsRow(
        data=event.data,
        context=event.context,
        entity_id=new_state.entity_id,
        state=new_state.state,
        context_id_bin=ulid_to_bytes(new_state.context.id),
        context_user_id=new_state.context.user_id,
        context_parent_id_bin=ulid_to_bytes_or_none(new_state.context.parent_id),
        time_fired_ts=dt_util.utc_to_timestamp(new_state.last_updated),
        state_id=hash(event),
        icon=new_state.attributes.get(ATTR_ICON),
    )
