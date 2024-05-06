"""Event parser and human readable log generator."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy.engine.row import Row

from homeassistant.components.recorder.filters import Filters
from homeassistant.components.recorder.models import (
    bytes_to_ulid_or_none,
    bytes_to_uuid_hex_or_none,
    ulid_to_bytes_or_none,
    uuid_hex_to_bytes_or_none,
)
from homeassistant.const import ATTR_ICON, EVENT_STATE_CHANGED
from homeassistant.core import Context, Event, State, callback
from homeassistant.util.json import json_loads
from homeassistant.util.ulid import ulid_to_bytes

if TYPE_CHECKING:
    from functools import cached_property
else:
    from homeassistant.backports.functools import cached_property


@dataclass(slots=True)
class LogbookConfig:
    """Configuration for the logbook integration."""

    external_events: dict[
        str, tuple[str, Callable[[LazyEventPartialState], dict[str, Any]]]
    ]
    sqlalchemy_filter: Filters | None = None
    entity_filter: Callable[[str], bool] | None = None


class LazyEventPartialState:
    """A lazy version of core Event with limited State joined in."""

    def __init__(
        self,
        row: Row | EventAsRow,
        event_data_cache: dict[str, dict[str, Any]],
    ) -> None:
        """Init the lazy event."""
        self.row = row
        self._event_data: dict[str, Any] | None = None
        self._event_data_cache = event_data_cache
        # We need to explicitly check for the row is EventAsRow as the unhappy path
        # to fetch row.data for Row is very expensive
        if type(row) is EventAsRow:  # noqa: E721
            # If its an EventAsRow we can avoid the whole
            # json decode process as we already have the data
            self.data = row.data
            return
        if TYPE_CHECKING:
            source = cast(str, row.event_data)
        else:
            source = row.event_data
        if not source:
            self.data = {}
        elif event_data := self._event_data_cache.get(source):
            self.data = event_data
        else:
            self.data = self._event_data_cache[source] = cast(
                dict[str, Any], json_loads(source)
            )

    @cached_property
    def event_type(self) -> str | None:
        """Return the event type."""
        return self.row.event_type

    @cached_property
    def entity_id(self) -> str | None:
        """Return the entity id."""
        return self.row.entity_id

    @cached_property
    def state(self) -> str | None:
        """Return the state."""
        return self.row.state

    @cached_property
    def context_id(self) -> str | None:
        """Return the context id."""
        return bytes_to_ulid_or_none(self.row.context_id_bin)

    @cached_property
    def context_user_id(self) -> str | None:
        """Return the context user id."""
        return bytes_to_uuid_hex_or_none(self.row.context_user_id_bin)

    @cached_property
    def context_parent_id(self) -> str | None:
        """Return the context parent id."""
        return bytes_to_ulid_or_none(self.row.context_parent_id_bin)


@dataclass(slots=True, frozen=True)
class EventAsRow:
    """Convert an event to a row."""

    data: dict[str, Any]
    context: Context
    context_id_bin: bytes
    time_fired_ts: float
    row_id: int
    event_data: str | None = None
    entity_id: str | None = None
    icon: str | None = None
    context_user_id_bin: bytes | None = None
    context_parent_id_bin: bytes | None = None
    event_type: str | None = None
    state: str | None = None
    context_only: None = None


@callback
def async_event_to_row(event: Event) -> EventAsRow:
    """Convert an event to a row."""
    if event.event_type != EVENT_STATE_CHANGED:
        context = event.context
        return EventAsRow(
            data=event.data,
            context=event.context,
            event_type=event.event_type,
            context_id_bin=ulid_to_bytes(context.id),
            context_user_id_bin=uuid_hex_to_bytes_or_none(context.user_id),
            context_parent_id_bin=ulid_to_bytes_or_none(context.parent_id),
            time_fired_ts=event.time_fired_timestamp,
            row_id=hash(event),
        )
    # States are prefiltered so we never get states
    # that are missing new_state or old_state
    # since the logbook does not show these
    new_state: State = event.data["new_state"]
    context = new_state.context
    return EventAsRow(
        data=event.data,
        context=event.context,
        entity_id=new_state.entity_id,
        state=new_state.state,
        context_id_bin=ulid_to_bytes(context.id),
        context_user_id_bin=uuid_hex_to_bytes_or_none(context.user_id),
        context_parent_id_bin=ulid_to_bytes_or_none(context.parent_id),
        time_fired_ts=new_state.last_updated_timestamp,
        row_id=hash(event),
        icon=new_state.attributes.get(ATTR_ICON),
    )
