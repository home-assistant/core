"""Event parser and human readable log generator."""
from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime as dt
from typing import Any

from sqlalchemy.engine import Result
from sqlalchemy.engine.row import Row

from homeassistant.components.recorder.filters import Filters
from homeassistant.components.recorder.models import (
    process_datetime_to_timestamp,
    process_timestamp_to_utc_isoformat,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
    ATTR_SERVICE,
    EVENT_CALL_SERVICE,
    EVENT_LOGBOOK_ENTRY,
)
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_MESSAGE,
    CONTEXT_DOMAIN,
    CONTEXT_ENTITY_ID,
    CONTEXT_ENTITY_ID_NAME,
    CONTEXT_EVENT_TYPE,
    CONTEXT_MESSAGE,
    CONTEXT_NAME,
    CONTEXT_SERVICE,
    CONTEXT_SOURCE,
    CONTEXT_STATE,
    CONTEXT_USER_ID,
    DOMAIN,
    LOGBOOK_ENTRY_DOMAIN,
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_ICON,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LOGBOOK_ENTRY_SOURCE,
    LOGBOOK_ENTRY_STATE,
    LOGBOOK_ENTRY_WHEN,
    LOGBOOK_FILTERS,
)
from .helpers import is_sensor_continuous
from .models import EventAsRow, LazyEventPartialState, async_event_to_row
from .queries import statement_for_request
from .queries.common import PSEUDO_EVENT_STATE_CHANGED


@dataclass
class LogbookRun:
    """A logbook run which may be a long running event stream or single request."""

    context_lookup: ContextLookup
    external_events: dict[
        str, tuple[str, Callable[[LazyEventPartialState], dict[str, Any]]]
    ]
    event_cache: EventCache
    entity_name_cache: EntityNameCache
    include_entity_name: bool
    format_time: Callable[[Row | EventAsRow], Any]


class EventProcessor:
    """Stream into logbook format."""

    def __init__(
        self,
        hass: HomeAssistant,
        event_types: tuple[str, ...],
        entity_ids: list[str] | None = None,
        device_ids: list[str] | None = None,
        context_id: str | None = None,
        timestamp: bool = False,
        include_entity_name: bool = True,
    ) -> None:
        """Init the event stream."""
        assert not (
            context_id and (entity_ids or device_ids)
        ), "can't pass in both context_id and (entity_ids or device_ids)"
        self.hass = hass
        self.ent_reg = er.async_get(hass)
        self.event_types = event_types
        self.entity_ids = entity_ids
        self.device_ids = device_ids
        self.context_id = context_id
        self.filters: Filters | None = hass.data[LOGBOOK_FILTERS]
        format_time = (
            _row_time_fired_timestamp if timestamp else _row_time_fired_isoformat
        )
        external_events: dict[
            str, tuple[str, Callable[[LazyEventPartialState], dict[str, Any]]]
        ] = hass.data.get(DOMAIN, {})
        self.logbook_run = LogbookRun(
            context_lookup=ContextLookup(hass),
            external_events=external_events,
            event_cache=EventCache({}),
            entity_name_cache=EntityNameCache(self.hass),
            include_entity_name=include_entity_name,
            format_time=format_time,
        )
        self.context_augmenter = ContextAugmenter(self.logbook_run)

    @property
    def limited_select(self) -> bool:
        """Check if the stream is limited by entities context or device ids."""
        return bool(self.entity_ids or self.context_id or self.device_ids)

    def switch_to_live(self) -> None:
        """Switch to live stream.

        Clear caches so we can reduce memory pressure.
        """
        self.logbook_run.event_cache.clear()
        self.logbook_run.context_lookup.clear()

    def get_events(
        self,
        start_day: dt,
        end_day: dt,
    ) -> list[dict[str, Any]]:
        """Get events for a period of time."""

        def yield_rows(result: Result) -> Sequence[Row] | Result:
            """Yield rows from the database."""
            # end_day - start_day intentionally checks .days and not .total_seconds()
            # since we don't want to switch over to buffered if they go
            # over one day by a few hours since the UI makes it so easy to do that.
            if self.limited_select or (end_day - start_day).days <= 1:
                return result.all()
            # Only buffer rows to reduce memory pressure
            # if we expect the result set is going to be very large.
            # What is considered very large is going to differ
            # based on the hardware Home Assistant is running on.
            #
            # sqlalchemy suggests that is at least 10k, but for
            # even and RPi3 that number seems higher in testing
            # so we don't switch over until we request > 1 day+ of data.
            #
            return result.yield_per(1024)

        stmt = statement_for_request(
            start_day,
            end_day,
            self.event_types,
            self.entity_ids,
            self.device_ids,
            self.filters,
            self.context_id,
        )
        with session_scope(hass=self.hass) as session:
            return self.humanify(yield_rows(session.execute(stmt)))

    def humanify(
        self, rows: Generator[EventAsRow, None, None] | Sequence[Row] | Result
    ) -> list[dict[str, str]]:
        """Humanify rows."""
        return list(
            _humanify(
                rows,
                self.ent_reg,
                self.logbook_run,
                self.context_augmenter,
            )
        )


def _humanify(
    rows: Generator[EventAsRow, None, None] | Sequence[Row] | Result,
    ent_reg: er.EntityRegistry,
    logbook_run: LogbookRun,
    context_augmenter: ContextAugmenter,
) -> Generator[dict[str, Any], None, None]:
    """Generate a converted list of events into entries."""
    # Continuous sensors, will be excluded from the logbook
    continuous_sensors: dict[str, bool] = {}
    context_lookup = logbook_run.context_lookup
    external_events = logbook_run.external_events
    event_cache = logbook_run.event_cache
    entity_name_cache = logbook_run.entity_name_cache
    include_entity_name = logbook_run.include_entity_name
    format_time = logbook_run.format_time

    # Process rows
    for row in rows:
        context_id = context_lookup.memorize(row)
        if row.context_only:
            continue
        event_type = row.event_type
        if event_type == EVENT_CALL_SERVICE:
            continue
        if event_type is PSEUDO_EVENT_STATE_CHANGED:
            entity_id = row.entity_id
            assert entity_id is not None
            # Skip continuous sensors
            if (
                is_continuous := continuous_sensors.get(entity_id)
            ) is None and split_entity_id(entity_id)[0] == SENSOR_DOMAIN:
                is_continuous = is_sensor_continuous(ent_reg, entity_id)
                continuous_sensors[entity_id] = is_continuous
            if is_continuous:
                continue

            data = {
                LOGBOOK_ENTRY_WHEN: format_time(row),
                LOGBOOK_ENTRY_STATE: row.state,
                LOGBOOK_ENTRY_ENTITY_ID: entity_id,
            }
            if include_entity_name:
                data[LOGBOOK_ENTRY_NAME] = entity_name_cache.get(entity_id)
            if icon := row.icon or row.old_format_icon:
                data[LOGBOOK_ENTRY_ICON] = icon

            context_augmenter.augment(data, row, context_id)
            yield data

        elif event_type in external_events:
            domain, describe_event = external_events[event_type]
            data = describe_event(event_cache.get(row))
            data[LOGBOOK_ENTRY_WHEN] = format_time(row)
            data[LOGBOOK_ENTRY_DOMAIN] = domain
            context_augmenter.augment(data, row, context_id)
            yield data

        elif event_type == EVENT_LOGBOOK_ENTRY:
            event = event_cache.get(row)
            if not (event_data := event.data):
                continue
            entry_domain = event_data.get(ATTR_DOMAIN)
            entry_entity_id = event_data.get(ATTR_ENTITY_ID)
            if entry_domain is None and entry_entity_id is not None:
                with suppress(IndexError):
                    entry_domain = split_entity_id(str(entry_entity_id))[0]
            data = {
                LOGBOOK_ENTRY_WHEN: format_time(row),
                LOGBOOK_ENTRY_NAME: event_data.get(ATTR_NAME),
                LOGBOOK_ENTRY_MESSAGE: event_data.get(ATTR_MESSAGE),
                LOGBOOK_ENTRY_DOMAIN: entry_domain,
                LOGBOOK_ENTRY_ENTITY_ID: entry_entity_id,
            }
            context_augmenter.augment(data, row, context_id)
            yield data


class ContextLookup:
    """A lookup class for context origins."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Memorize context origin."""
        self.hass = hass
        self._memorize_new = True
        self._lookup: dict[str | None, Row | EventAsRow | None] = {None: None}

    def memorize(self, row: Row | EventAsRow) -> str | None:
        """Memorize a context from the database."""
        if self._memorize_new:
            context_id: str = row.context_id
            self._lookup.setdefault(context_id, row)
            return context_id
        return None

    def clear(self) -> None:
        """Clear the context origins and stop recording new ones."""
        self._lookup.clear()
        self._memorize_new = False

    def get(self, context_id: str) -> Row | EventAsRow | None:
        """Get the context origin."""
        return self._lookup.get(context_id)


class ContextAugmenter:
    """Augment data with context trace."""

    def __init__(self, logbook_run: LogbookRun) -> None:
        """Init the augmenter."""
        self.context_lookup = logbook_run.context_lookup
        self.entity_name_cache = logbook_run.entity_name_cache
        self.external_events = logbook_run.external_events
        self.event_cache = logbook_run.event_cache
        self.include_entity_name = logbook_run.include_entity_name

    def _get_context_row(
        self, context_id: str | None, row: Row | EventAsRow
    ) -> Row | EventAsRow | None:
        """Get the context row from the id or row context."""
        if context_id:
            return self.context_lookup.get(context_id)
        if (context := getattr(row, "context", None)) is not None and (
            origin_event := context.origin_event
        ) is not None:
            return async_event_to_row(origin_event)
        return None

    def augment(
        self, data: dict[str, Any], row: Row | EventAsRow, context_id: str | None
    ) -> None:
        """Augment data from the row and cache."""
        if context_user_id := row.context_user_id:
            data[CONTEXT_USER_ID] = context_user_id

        if not (context_row := self._get_context_row(context_id, row)):
            return

        if _rows_match(row, context_row):
            # This is the first event with the given ID. Was it directly caused by
            # a parent event?
            if (
                not row.context_parent_id
                or (
                    context_row := self._get_context_row(
                        row.context_parent_id, context_row
                    )
                )
                is None
            ):
                return
            # Ensure the (parent) context_event exists and is not the root cause of
            # this log entry.
            if _rows_match(row, context_row):
                return
        event_type = context_row.event_type
        # State change
        if context_entity_id := context_row.entity_id:
            data[CONTEXT_STATE] = context_row.state
            data[CONTEXT_ENTITY_ID] = context_entity_id
            if self.include_entity_name:
                data[CONTEXT_ENTITY_ID_NAME] = self.entity_name_cache.get(
                    context_entity_id
                )
            return

        # Call service
        if event_type == EVENT_CALL_SERVICE:
            event = self.event_cache.get(context_row)
            event_data = event.data
            data[CONTEXT_DOMAIN] = event_data.get(ATTR_DOMAIN)
            data[CONTEXT_SERVICE] = event_data.get(ATTR_SERVICE)
            data[CONTEXT_EVENT_TYPE] = event_type
            return

        if event_type not in self.external_events:
            return

        domain, describe_event = self.external_events[event_type]
        data[CONTEXT_EVENT_TYPE] = event_type
        data[CONTEXT_DOMAIN] = domain
        event = self.event_cache.get(context_row)
        described = describe_event(event)
        if name := described.get(LOGBOOK_ENTRY_NAME):
            data[CONTEXT_NAME] = name
        if message := described.get(LOGBOOK_ENTRY_MESSAGE):
            data[CONTEXT_MESSAGE] = message
        # In 2022.12 and later drop `CONTEXT_MESSAGE` if `CONTEXT_SOURCE` is available
        if source := described.get(LOGBOOK_ENTRY_SOURCE):
            data[CONTEXT_SOURCE] = source
        if not (attr_entity_id := described.get(LOGBOOK_ENTRY_ENTITY_ID)):
            return
        data[CONTEXT_ENTITY_ID] = attr_entity_id
        if self.include_entity_name:
            data[CONTEXT_ENTITY_ID_NAME] = self.entity_name_cache.get(attr_entity_id)


def _rows_match(row: Row | EventAsRow, other_row: Row | EventAsRow) -> bool:
    """Check of rows match by using the same method as Events __hash__."""
    if (
        row is other_row
        or (state_id := row.state_id)
        and state_id == other_row.state_id
        or (event_id := row.event_id)
        and event_id == other_row.event_id
    ):
        return True
    return False


def _row_time_fired_isoformat(row: Row | EventAsRow) -> str:
    """Convert the row timed_fired to isoformat."""
    return process_timestamp_to_utc_isoformat(
        dt_util.utc_from_timestamp(row.time_fired_ts) or dt_util.utcnow()
    )


def _row_time_fired_timestamp(row: Row | EventAsRow) -> float:
    """Convert the row timed_fired to timestamp."""
    return row.time_fired_ts or process_datetime_to_timestamp(dt_util.utcnow())


class EntityNameCache:
    """A cache to lookup the name for an entity.

    This class should not be used to lookup attributes
    that are expected to change state.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the cache."""
        self._hass = hass
        self._names: dict[str, str] = {}

    def get(self, entity_id: str) -> str:
        """Lookup an the friendly name."""
        if entity_id in self._names:
            return self._names[entity_id]
        if (current_state := self._hass.states.get(entity_id)) and (
            friendly_name := current_state.attributes.get(ATTR_FRIENDLY_NAME)
        ):
            self._names[entity_id] = friendly_name
        else:
            return split_entity_id(entity_id)[1].replace("_", " ")

        return self._names[entity_id]


class EventCache:
    """Cache LazyEventPartialState by row."""

    def __init__(self, event_data_cache: dict[str, dict[str, Any]]) -> None:
        """Init the cache."""
        self._event_data_cache = event_data_cache
        self.event_cache: dict[Row | EventAsRow, LazyEventPartialState] = {}

    def get(self, row: EventAsRow | Row) -> LazyEventPartialState:
        """Get the event from the row."""
        if isinstance(row, EventAsRow):
            return LazyEventPartialState(row, self._event_data_cache)
        if event := self.event_cache.get(row):
            return event
        self.event_cache[row] = lazy_event = LazyEventPartialState(
            row, self._event_data_cache
        )
        return lazy_event

    def clear(self) -> None:
        """Clear the event cache."""
        self._event_data_cache = {}
        self.event_cache = {}
