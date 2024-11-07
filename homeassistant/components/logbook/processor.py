"""Event parser and human readable log generator."""

from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass
from datetime import datetime as dt
import logging
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy.engine import Result
from sqlalchemy.engine.row import Row

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.filters import Filters
from homeassistant.components.recorder.models import (
    bytes_to_uuid_hex_or_none,
    extract_event_type_ids,
    extract_metadata_ids,
    process_timestamp_to_utc_isoformat,
)
from homeassistant.components.recorder.util import (
    execute_stmt_lambda_element,
    session_scope,
)
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
from homeassistant.util.event_type import EventType

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
)
from .helpers import is_sensor_continuous
from .models import (
    CONTEXT_ID_BIN_POS,
    CONTEXT_ONLY_POS,
    CONTEXT_PARENT_ID_BIN_POS,
    CONTEXT_POS,
    CONTEXT_USER_ID_BIN_POS,
    ENTITY_ID_POS,
    EVENT_TYPE_POS,
    ICON_POS,
    ROW_ID_POS,
    STATE_POS,
    TIME_FIRED_TS_POS,
    EventAsRow,
    LazyEventPartialState,
    LogbookConfig,
    async_event_to_row,
)
from .queries import statement_for_request
from .queries.common import PSEUDO_EVENT_STATE_CHANGED

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class LogbookRun:
    """A logbook run which may be a long running event stream or single request."""

    context_lookup: dict[bytes | None, Row | EventAsRow | None]
    external_events: dict[
        EventType[Any] | str,
        tuple[str, Callable[[LazyEventPartialState], dict[str, Any]]],
    ]
    event_cache: EventCache
    entity_name_cache: EntityNameCache
    include_entity_name: bool
    timestamp: bool
    memoize_new_contexts: bool = True


class EventProcessor:
    """Stream into logbook format."""

    def __init__(
        self,
        hass: HomeAssistant,
        event_types: tuple[EventType[Any] | str, ...],
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
        logbook_config: LogbookConfig = hass.data[DOMAIN]
        self.filters: Filters | None = logbook_config.sqlalchemy_filter
        self.logbook_run = LogbookRun(
            context_lookup={None: None},
            external_events=logbook_config.external_events,
            event_cache=EventCache({}),
            entity_name_cache=EntityNameCache(self.hass),
            include_entity_name=include_entity_name,
            timestamp=timestamp,
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
        self.logbook_run.memoize_new_contexts = False

    def get_events(
        self,
        start_day: dt,
        end_day: dt,
    ) -> list[dict[str, Any]]:
        """Get events for a period of time."""
        with session_scope(hass=self.hass, read_only=True) as session:
            metadata_ids: list[int] | None = None
            instance = get_instance(self.hass)
            if self.entity_ids:
                metadata_ids = extract_metadata_ids(
                    instance.states_meta_manager.get_many(
                        self.entity_ids, session, False
                    )
                )
            event_type_ids = tuple(
                extract_event_type_ids(
                    instance.event_type_manager.get_many(self.event_types, session)
                )
            )
            stmt = statement_for_request(
                start_day,
                end_day,
                event_type_ids,
                self.entity_ids,
                metadata_ids,
                self.device_ids,
                self.filters,
                self.context_id,
            )
            return self.humanify(
                execute_stmt_lambda_element(session, stmt, orm_rows=False)
            )

    def humanify(
        self, rows: Generator[EventAsRow] | Sequence[Row] | Result
    ) -> list[dict[str, str]]:
        """Humanify rows."""
        return list(
            _humanify(
                self.hass,
                rows,
                self.ent_reg,
                self.logbook_run,
                self.context_augmenter,
            )
        )


def _humanify(
    hass: HomeAssistant,
    rows: Generator[EventAsRow] | Sequence[Row] | Result,
    ent_reg: er.EntityRegistry,
    logbook_run: LogbookRun,
    context_augmenter: ContextAugmenter,
) -> Generator[dict[str, Any]]:
    """Generate a converted list of events into entries."""
    # Continuous sensors, will be excluded from the logbook
    continuous_sensors: dict[str, bool] = {}
    context_lookup = logbook_run.context_lookup
    external_events = logbook_run.external_events
    event_cache_get = logbook_run.event_cache.get
    entity_name_cache_get = logbook_run.entity_name_cache.get
    include_entity_name = logbook_run.include_entity_name
    timestamp = logbook_run.timestamp
    memoize_new_contexts = logbook_run.memoize_new_contexts
    get_context = context_augmenter.get_context
    context_id_bin: bytes
    data: dict[str, Any]

    # Process rows
    for row in rows:
        context_id_bin = row[CONTEXT_ID_BIN_POS]
        if memoize_new_contexts and context_id_bin not in context_lookup:
            context_lookup[context_id_bin] = row
        if row[CONTEXT_ONLY_POS]:
            continue
        event_type = row[EVENT_TYPE_POS]
        if event_type == EVENT_CALL_SERVICE:
            continue

        if event_type is PSEUDO_EVENT_STATE_CHANGED:
            entity_id = row[ENTITY_ID_POS]
            if TYPE_CHECKING:
                assert entity_id is not None
            # Skip continuous sensors
            if (
                is_continuous := continuous_sensors.get(entity_id)
            ) is None and split_entity_id(entity_id)[0] == SENSOR_DOMAIN:
                is_continuous = is_sensor_continuous(hass, ent_reg, entity_id)
                continuous_sensors[entity_id] = is_continuous
            if is_continuous:
                continue

            data = {
                LOGBOOK_ENTRY_STATE: row[STATE_POS],
                LOGBOOK_ENTRY_ENTITY_ID: entity_id,
            }
            if include_entity_name:
                data[LOGBOOK_ENTRY_NAME] = entity_name_cache_get(entity_id)
            if icon := row[ICON_POS]:
                data[LOGBOOK_ENTRY_ICON] = icon

        elif event_type in external_events:
            domain, describe_event = external_events[event_type]
            try:
                data = describe_event(event_cache_get(row))
            except Exception:
                _LOGGER.exception(
                    "Error with %s describe event for %s", domain, event_type
                )
                continue
            data[LOGBOOK_ENTRY_DOMAIN] = domain

        elif event_type == EVENT_LOGBOOK_ENTRY:
            event = event_cache_get(row)
            if not (event_data := event.data):
                continue
            entry_domain = event_data.get(ATTR_DOMAIN)
            entry_entity_id = event_data.get(ATTR_ENTITY_ID)
            if entry_domain is None and entry_entity_id is not None:
                entry_domain = split_entity_id(str(entry_entity_id))[0]
            data = {
                LOGBOOK_ENTRY_NAME: event_data.get(ATTR_NAME),
                LOGBOOK_ENTRY_MESSAGE: event_data.get(ATTR_MESSAGE),
                LOGBOOK_ENTRY_DOMAIN: entry_domain,
                LOGBOOK_ENTRY_ENTITY_ID: entry_entity_id,
            }

        else:
            continue

        time_fired_ts = row[TIME_FIRED_TS_POS]
        if timestamp:
            when = time_fired_ts or time.time()
        else:
            when = process_timestamp_to_utc_isoformat(
                dt_util.utc_from_timestamp(time_fired_ts) or dt_util.utcnow()
            )
        data[LOGBOOK_ENTRY_WHEN] = when

        if context_user_id_bin := row[CONTEXT_USER_ID_BIN_POS]:
            data[CONTEXT_USER_ID] = bytes_to_uuid_hex_or_none(context_user_id_bin)

        # Augment context if its available but not if the context is the same as the row
        # or if the context is the parent of the row
        if (context_row := get_context(context_id_bin, row)) and not (
            (row is context_row or _rows_ids_match(row, context_row))
            and (
                not (context_parent := row[CONTEXT_PARENT_ID_BIN_POS])
                or not (context_row := get_context(context_parent, context_row))
                or row is context_row
                or _rows_ids_match(row, context_row)
            )
        ):
            context_augmenter.augment(data, context_row)

        yield data


class ContextAugmenter:
    """Augment data with context trace."""

    def __init__(self, logbook_run: LogbookRun) -> None:
        """Init the augmenter."""
        self.context_lookup = logbook_run.context_lookup
        self.entity_name_cache = logbook_run.entity_name_cache
        self.external_events = logbook_run.external_events
        self.event_cache = logbook_run.event_cache
        self.include_entity_name = logbook_run.include_entity_name

    def get_context(
        self, context_id_bin: bytes | None, row: Row | EventAsRow | None
    ) -> Row | EventAsRow | None:
        """Get the context row from the id or row context."""
        if context_id_bin is not None and (
            context_row := self.context_lookup.get(context_id_bin)
        ):
            return context_row
        if (
            type(row) is EventAsRow
            and (context := row[CONTEXT_POS]) is not None
            and (origin_event := context.origin_event) is not None
        ):
            return async_event_to_row(origin_event)
        return None

    def augment(self, data: dict[str, Any], context_row: Row | EventAsRow) -> None:
        """Augment data from the row and cache."""
        event_type = context_row[EVENT_TYPE_POS]
        # State change
        if context_entity_id := context_row[ENTITY_ID_POS]:
            data[CONTEXT_STATE] = context_row[STATE_POS]
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
        try:
            described = describe_event(event)
        except Exception:
            _LOGGER.exception("Error with %s describe event for %s", domain, event_type)
            return
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


def _rows_ids_match(row: Row | EventAsRow, other_row: Row | EventAsRow) -> bool:
    """Check of rows match by using the same method as Events __hash__."""
    return bool((row_id := row[ROW_ID_POS]) and row_id == other_row[ROW_ID_POS])


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
        if type(row) is EventAsRow:  # - this is never subclassed
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
