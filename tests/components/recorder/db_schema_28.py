"""Models for SQLAlchemy.

This file contains the model definitions for schema version 28.
It is used to test the schema migration logic.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import time
from typing import Any, TypedDict, cast, overload

from fnv_hash_fast import fnv1a_32
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    distinct,
)
from sqlalchemy.dialects import mysql, oracle, postgresql
from sqlalchemy.engine.row import Row
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.orm.session import Session

from homeassistant.components.recorder.const import ALL_DOMAIN_EXCLUDE_ATTRS, JSON_DUMP
from homeassistant.const import (
    MAX_LENGTH_EVENT_CONTEXT_ID,
    MAX_LENGTH_EVENT_EVENT_TYPE,
    MAX_LENGTH_EVENT_ORIGIN,
    MAX_LENGTH_STATE_ENTITY_ID,
    MAX_LENGTH_STATE_STATE,
)
from homeassistant.core import Context, Event, EventOrigin, State, split_entity_id
import homeassistant.util.dt as dt_util

# SQLAlchemy Schema
Base = declarative_base()

SCHEMA_VERSION = 28

_LOGGER = logging.getLogger(__name__)

DB_TIMEZONE = "+00:00"

TABLE_EVENTS = "events"
TABLE_EVENT_DATA = "event_data"
TABLE_EVENT_TYPES = "event_types"
TABLE_STATES = "states"
TABLE_STATES_META = "states_meta"
TABLE_STATE_ATTRIBUTES = "state_attributes"
TABLE_RECORDER_RUNS = "recorder_runs"
TABLE_SCHEMA_CHANGES = "schema_changes"
TABLE_STATISTICS = "statistics"
TABLE_STATISTICS_META = "statistics_meta"
TABLE_STATISTICS_RUNS = "statistics_runs"
TABLE_STATISTICS_SHORT_TERM = "statistics_short_term"

ALL_TABLES = [
    TABLE_STATES,
    TABLE_STATE_ATTRIBUTES,
    TABLE_EVENTS,
    TABLE_EVENT_DATA,
    TABLE_EVENT_TYPES,
    TABLE_RECORDER_RUNS,
    TABLE_SCHEMA_CHANGES,
    TABLE_STATISTICS,
    TABLE_STATISTICS_META,
    TABLE_STATISTICS_RUNS,
    TABLE_STATISTICS_SHORT_TERM,
]

TABLES_TO_CHECK = [
    TABLE_STATES,
    TABLE_EVENTS,
    TABLE_RECORDER_RUNS,
    TABLE_SCHEMA_CHANGES,
]


EMPTY_JSON_OBJECT = "{}"


DATETIME_TYPE = DateTime(timezone=True).with_variant(
    mysql.DATETIME(timezone=True, fsp=6), "mysql"
)
DOUBLE_TYPE = (
    Float()
    .with_variant(mysql.DOUBLE(asdecimal=False), "mysql")
    .with_variant(oracle.DOUBLE_PRECISION(), "oracle")
    .with_variant(postgresql.DOUBLE_PRECISION(), "postgresql")
)
EVENT_ORIGIN_ORDER = [EventOrigin.local, EventOrigin.remote]
EVENT_ORIGIN_TO_IDX = {origin: idx for idx, origin in enumerate(EVENT_ORIGIN_ORDER)}
CONTEXT_ID_BIN_MAX_LENGTH = 16
EVENTS_CONTEXT_ID_BIN_INDEX = "ix_events_context_id_bin"
STATES_CONTEXT_ID_BIN_INDEX = "ix_states_context_id_bin"

TIMESTAMP_TYPE = DOUBLE_TYPE


class Events(Base):  # type: ignore[misc,valid-type]
    """Event history data."""

    __table_args__ = (
        # Used for fetching events at a specific time
        # see logbook
        Index("ix_events_event_type_time_fired", "event_type", "time_fired"),
        Index(
            EVENTS_CONTEXT_ID_BIN_INDEX,
            "context_id_bin",
            mysql_length=CONTEXT_ID_BIN_MAX_LENGTH,
            mariadb_length=CONTEXT_ID_BIN_MAX_LENGTH,
        ),
        {"mysql_default_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    __tablename__ = TABLE_EVENTS
    event_id = Column(Integer, Identity(), primary_key=True)  # no longer used
    event_type = Column(String(MAX_LENGTH_EVENT_EVENT_TYPE))
    event_data = Column(Text().with_variant(mysql.LONGTEXT, "mysql"))
    origin = Column(String(MAX_LENGTH_EVENT_ORIGIN))  # no longer used
    origin_idx = Column(SmallInteger)
    time_fired = Column(DATETIME_TYPE, index=True)
    time_fired_ts = Column(
        TIMESTAMP_TYPE, index=True
    )  # *** Not originally in v28, only added for recorder to startup ok
    context_id = Column(String(MAX_LENGTH_EVENT_CONTEXT_ID), index=True)
    context_user_id = Column(String(MAX_LENGTH_EVENT_CONTEXT_ID))
    context_parent_id = Column(String(MAX_LENGTH_EVENT_CONTEXT_ID))
    data_id = Column(Integer, ForeignKey("event_data.data_id"), index=True)
    context_id_bin = Column(
        LargeBinary(CONTEXT_ID_BIN_MAX_LENGTH)
    )  # *** Not originally in v28, only added for recorder to startup ok
    context_user_id_bin = Column(
        LargeBinary(CONTEXT_ID_BIN_MAX_LENGTH)
    )  # *** Not originally in v28, only added for recorder to startup ok
    context_parent_id_bin = Column(
        LargeBinary(CONTEXT_ID_BIN_MAX_LENGTH)
    )  # *** Not originally in v28, only added for recorder to startup ok
    event_type_id = Column(
        Integer, ForeignKey("event_types.event_type_id"), index=True
    )  # *** Not originally in v28, only added for recorder to startup ok
    event_data_rel = relationship("EventData")
    event_type_rel = relationship("EventTypes")

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.Events("
            f"id={self.event_id}, type='{self.event_type}', "
            f"origin_idx='{self.origin_idx}', time_fired='{self.time_fired}'"
            f", data_id={self.data_id})>"
        )

    @staticmethod
    def from_event(event: Event) -> Events:
        """Create an event database object from a native event."""
        return Events(
            event_type=event.event_type,
            event_data=None,
            origin_idx=EVENT_ORIGIN_TO_IDX.get(event.origin),
            time_fired=event.time_fired,
            context_id=event.context.id,
            context_user_id=event.context.user_id,
            context_parent_id=event.context.parent_id,
        )

    def to_native(self, validate_entity_id: bool = True) -> Event | None:
        """Convert to a native HA Event."""
        context = Context(
            id=self.context_id,
            user_id=self.context_user_id,
            parent_id=self.context_parent_id,
        )
        try:
            return Event(
                self.event_type,
                json.loads(self.event_data) if self.event_data else {},
                EventOrigin(self.origin)
                if self.origin
                else EVENT_ORIGIN_ORDER[self.origin_idx],
                process_timestamp(self.time_fired),
                context=context,
            )
        except ValueError:
            # When json.loads fails
            _LOGGER.exception("Error converting to event: %s", self)
            return None


class EventData(Base):  # type: ignore[misc,valid-type]
    """Event data history."""

    __table_args__ = (
        {"mysql_default_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    __tablename__ = TABLE_EVENT_DATA
    data_id = Column(Integer, Identity(), primary_key=True)
    hash = Column(BigInteger, index=True)
    # Note that this is not named attributes to avoid confusion with the states table
    shared_data = Column(Text().with_variant(mysql.LONGTEXT, "mysql"))

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.EventData("
            f"id={self.data_id}, hash='{self.hash}', data='{self.shared_data}'"
            f")>"
        )

    @staticmethod
    def from_event(event: Event) -> EventData:
        """Create object from an event."""
        shared_data = JSON_DUMP(event.data)
        return EventData(
            shared_data=shared_data, hash=EventData.hash_shared_data(shared_data)
        )

    @staticmethod
    def shared_data_from_event(event: Event) -> str:
        """Create shared_attrs from an event."""
        return JSON_DUMP(event.data)

    @staticmethod
    def hash_shared_data(shared_data: str) -> int:
        """Return the hash of json encoded shared data."""
        return cast(int, fnv1a_32(shared_data.encode("utf-8")))

    def to_native(self) -> dict[str, Any]:
        """Convert to an HA state object."""
        try:
            return cast(dict[str, Any], json.loads(self.shared_data))
        except ValueError:
            _LOGGER.exception("Error converting row to event data: %s", self)
            return {}


# *** Not originally in v28, only added for recorder to startup ok
# This is not being tested by the v28 statistics migration tests
class EventTypes(Base):  # type: ignore[misc,valid-type]
    """Event type history."""

    __table_args__ = (
        {"mysql_default_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    __tablename__ = TABLE_EVENT_TYPES
    event_type_id = Column(Integer, Identity(), primary_key=True)
    event_type = Column(String(MAX_LENGTH_EVENT_EVENT_TYPE))


class States(Base):  # type: ignore[misc,valid-type]
    """State change history."""

    __table_args__ = (
        # Used for fetching the state of entities at a specific time
        # (get_states in history.py)
        Index("ix_states_entity_id_last_updated", "entity_id", "last_updated"),
        {"mysql_default_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    __tablename__ = TABLE_STATES
    state_id = Column(Integer, Identity(), primary_key=True)
    entity_id = Column(String(MAX_LENGTH_STATE_ENTITY_ID))
    state = Column(String(MAX_LENGTH_STATE_STATE))
    attributes = Column(Text().with_variant(mysql.LONGTEXT, "mysql"))
    event_id = Column(
        Integer, ForeignKey("events.event_id", ondelete="CASCADE"), index=True
    )
    last_changed = Column(DATETIME_TYPE, default=dt_util.utcnow)
    last_changed_ts = Column(
        TIMESTAMP_TYPE
    )  # *** Not originally in v30, only added for recorder to startup ok
    last_updated = Column(DATETIME_TYPE, default=dt_util.utcnow, index=True)
    last_updated_ts = Column(
        TIMESTAMP_TYPE, default=time.time, index=True
    )  # *** Not originally in v30, only added for recorder to startup ok
    old_state_id = Column(Integer, ForeignKey("states.state_id"), index=True)
    attributes_id = Column(
        Integer, ForeignKey("state_attributes.attributes_id"), index=True
    )
    context_id = Column(String(MAX_LENGTH_EVENT_CONTEXT_ID), index=True)
    context_user_id = Column(String(MAX_LENGTH_EVENT_CONTEXT_ID))
    context_parent_id = Column(String(MAX_LENGTH_EVENT_CONTEXT_ID))
    origin_idx = Column(SmallInteger)  # 0 is local, 1 is remote
    context_id_bin = Column(
        LargeBinary(CONTEXT_ID_BIN_MAX_LENGTH)
    )  # *** Not originally in v28, only added for recorder to startup ok
    context_user_id_bin = Column(
        LargeBinary(CONTEXT_ID_BIN_MAX_LENGTH)
    )  # *** Not originally in v28, only added for recorder to startup ok
    context_parent_id_bin = Column(
        LargeBinary(CONTEXT_ID_BIN_MAX_LENGTH)
    )  # *** Not originally in v28, only added for recorder to startup ok
    metadata_id = Column(
        Integer, ForeignKey("states_meta.metadata_id"), index=True
    )  # *** Not originally in v28, only added for recorder to startup ok
    states_meta_rel = relationship("StatesMeta")
    old_state = relationship("States", remote_side=[state_id])
    state_attributes = relationship("StateAttributes")

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.States("
            f"id={self.state_id}, entity_id='{self.entity_id}', "
            f"state='{self.state}', event_id='{self.event_id}', "
            f"last_updated='{self.last_updated.isoformat(sep=' ', timespec='seconds')}', "
            f"old_state_id={self.old_state_id}, attributes_id={self.attributes_id}"
            f")>"
        )

    @staticmethod
    def from_event(event: Event) -> States:
        """Create object from a state_changed event."""
        entity_id = event.data["entity_id"]
        state: State | None = event.data.get("new_state")
        dbstate = States(
            entity_id=entity_id,
            attributes=None,
            context_id=event.context.id,
            context_user_id=event.context.user_id,
            context_parent_id=event.context.parent_id,
            origin_idx=EVENT_ORIGIN_TO_IDX.get(event.origin),
        )

        # None state means the state was removed from the state machine
        if state is None:
            dbstate.state = ""
            dbstate.last_changed = event.time_fired
            dbstate.last_updated = event.time_fired
        else:
            dbstate.state = state.state
            dbstate.last_changed = state.last_changed
            dbstate.last_updated = state.last_updated

        return dbstate

    def to_native(self, validate_entity_id: bool = True) -> State | None:
        """Convert to an HA state object."""
        context = Context(
            id=self.context_id,
            user_id=self.context_user_id,
            parent_id=self.context_parent_id,
        )
        try:
            return State(
                self.entity_id,
                self.state,
                # Join the state_attributes table on attributes_id to get the attributes
                # for newer states
                json.loads(self.attributes) if self.attributes else {},
                process_timestamp(self.last_changed),
                process_timestamp(self.last_updated),
                context=context,
                validate_entity_id=validate_entity_id,
            )
        except ValueError:
            # When json.loads fails
            _LOGGER.exception("Error converting row to state: %s", self)
            return None


class StateAttributes(Base):  # type: ignore[misc,valid-type]
    """State attribute change history."""

    __table_args__ = (
        {"mysql_default_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    __tablename__ = TABLE_STATE_ATTRIBUTES
    attributes_id = Column(Integer, Identity(), primary_key=True)
    hash = Column(BigInteger, index=True)
    # Note that this is not named attributes to avoid confusion with the states table
    shared_attrs = Column(Text().with_variant(mysql.LONGTEXT, "mysql"))

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.StateAttributes("
            f"id={self.attributes_id}, hash='{self.hash}', attributes='{self.shared_attrs}'"
            f")>"
        )

    @staticmethod
    def from_event(event: Event) -> StateAttributes:
        """Create object from a state_changed event."""
        state: State | None = event.data.get("new_state")
        # None state means the state was removed from the state machine
        dbstate = StateAttributes(
            shared_attrs="{}" if state is None else JSON_DUMP(state.attributes)
        )
        dbstate.hash = StateAttributes.hash_shared_attrs(dbstate.shared_attrs)
        return dbstate

    @staticmethod
    def shared_attrs_from_event(
        event: Event, exclude_attrs_by_domain: dict[str, set[str]]
    ) -> str:
        """Create shared_attrs from a state_changed event."""
        state: State | None = event.data.get("new_state")
        # None state means the state was removed from the state machine
        if state is None:
            return "{}"
        domain = split_entity_id(state.entity_id)[0]
        exclude_attrs = (
            exclude_attrs_by_domain.get(domain, set()) | ALL_DOMAIN_EXCLUDE_ATTRS
        )
        return JSON_DUMP(
            {k: v for k, v in state.attributes.items() if k not in exclude_attrs}
        )

    @staticmethod
    def hash_shared_attrs(shared_attrs: str) -> int:
        """Return the hash of json encoded shared attributes."""
        return cast(int, fnv1a_32(shared_attrs.encode("utf-8")))

    def to_native(self) -> dict[str, Any]:
        """Convert to an HA state object."""
        try:
            return cast(dict[str, Any], json.loads(self.shared_attrs))
        except ValueError:
            # When json.loads fails
            _LOGGER.exception("Error converting row to state attributes: %s", self)
            return {}


# *** Not originally in v23, only added for recorder to startup ok
# This is not being tested by the v23 statistics migration tests
class StatesMeta(Base):  # type: ignore[misc,valid-type]
    """Metadata for states."""

    __table_args__ = (
        {"mysql_default_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    __tablename__ = TABLE_STATES_META
    metadata_id = Column(Integer, Identity(), primary_key=True)
    entity_id = Column(String(MAX_LENGTH_STATE_ENTITY_ID))

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            "<recorder.StatesMeta("
            f"id={self.metadata_id}, entity_id='{self.entity_id}'"
            ")>"
        )


class StatisticResult(TypedDict):
    """Statistic result data class.

    Allows multiple datapoints for the same statistic_id.
    """

    meta: StatisticMetaData
    stat: StatisticData


class StatisticDataBase(TypedDict):
    """Mandatory fields for statistic data class."""

    start: datetime


class StatisticData(StatisticDataBase, total=False):
    """Statistic data class."""

    mean: float
    min: float
    max: float
    last_reset: datetime | None
    state: float
    sum: float


class StatisticsBase:
    """Statistics base class."""

    id = Column(Integer, Identity(), primary_key=True)
    created = Column(DATETIME_TYPE, default=dt_util.utcnow)
    metadata_id = Column(
        Integer,
        ForeignKey(f"{TABLE_STATISTICS_META}.id", ondelete="CASCADE"),
        index=True,
    )
    start = Column(DATETIME_TYPE, index=True)
    mean = Column(DOUBLE_TYPE)
    min = Column(DOUBLE_TYPE)
    max = Column(DOUBLE_TYPE)
    last_reset = Column(DATETIME_TYPE)
    state = Column(DOUBLE_TYPE)
    sum = Column(DOUBLE_TYPE)

    @classmethod
    def from_stats(cls, metadata_id: int, stats: StatisticData) -> StatisticsBase:
        """Create object from a statistics."""
        return cls(  # type: ignore[call-arg,misc]
            metadata_id=metadata_id,
            **stats,
        )


class Statistics(Base, StatisticsBase):  # type: ignore[misc,valid-type]
    """Long term statistics."""

    duration = timedelta(hours=1)

    __table_args__ = (
        # Used for fetching statistics for a certain entity at a specific time
        Index("ix_statistics_statistic_id_start", "metadata_id", "start", unique=True),
    )
    __tablename__ = TABLE_STATISTICS


class StatisticsShortTerm(Base, StatisticsBase):  # type: ignore[misc,valid-type]
    """Short term statistics."""

    duration = timedelta(minutes=5)

    __table_args__ = (
        # Used for fetching statistics for a certain entity at a specific time
        Index(
            "ix_statistics_short_term_statistic_id_start",
            "metadata_id",
            "start",
            unique=True,
        ),
    )
    __tablename__ = TABLE_STATISTICS_SHORT_TERM


class StatisticMetaData(TypedDict):
    """Statistic meta data class."""

    has_mean: bool
    has_sum: bool
    name: str | None
    source: str
    statistic_id: str
    unit_of_measurement: str | None


class StatisticsMeta(Base):  # type: ignore[misc,valid-type]
    """Statistics meta data."""

    __table_args__ = (
        {"mysql_default_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    __tablename__ = TABLE_STATISTICS_META
    id = Column(Integer, Identity(), primary_key=True)
    statistic_id = Column(String(255), index=True)
    source = Column(String(32))
    unit_of_measurement = Column(String(255))
    has_mean = Column(Boolean)
    has_sum = Column(Boolean)
    name = Column(String(255))

    @staticmethod
    def from_meta(meta: StatisticMetaData) -> StatisticsMeta:
        """Create object from meta data."""
        return StatisticsMeta(**meta)


class RecorderRuns(Base):  # type: ignore[misc,valid-type]
    """Representation of recorder run."""

    __table_args__ = (Index("ix_recorder_runs_start_end", "start", "end"),)
    __tablename__ = TABLE_RECORDER_RUNS
    run_id = Column(Integer, Identity(), primary_key=True)
    start = Column(DateTime(timezone=True), default=dt_util.utcnow)
    end = Column(DateTime(timezone=True))
    closed_incorrect = Column(Boolean, default=False)
    created = Column(DateTime(timezone=True), default=dt_util.utcnow)

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        end = (
            f"'{self.end.isoformat(sep=' ', timespec='seconds')}'" if self.end else None
        )
        return (
            f"<recorder.RecorderRuns("
            f"id={self.run_id}, start='{self.start.isoformat(sep=' ', timespec='seconds')}', "
            f"end={end}, closed_incorrect={self.closed_incorrect}, "
            f"created='{self.created.isoformat(sep=' ', timespec='seconds')}'"
            f")>"
        )

    def entity_ids(self, point_in_time: datetime | None = None) -> list[str]:
        """Return the entity ids that existed in this run.

        Specify point_in_time if you want to know which existed at that point
        in time inside the run.
        """
        session = Session.object_session(self)

        assert session is not None, "RecorderRuns need to be persisted"

        query = session.query(distinct(States.entity_id)).filter(
            States.last_updated >= self.start
        )

        if point_in_time is not None:
            query = query.filter(States.last_updated < point_in_time)
        elif self.end is not None:
            query = query.filter(States.last_updated < self.end)

        return [row[0] for row in query]

    def to_native(self, validate_entity_id: bool = True) -> RecorderRuns:
        """Return self, native format is this model."""
        return self


class SchemaChanges(Base):  # type: ignore[misc,valid-type]
    """Representation of schema version changes."""

    __tablename__ = TABLE_SCHEMA_CHANGES
    change_id = Column(Integer, Identity(), primary_key=True)
    schema_version = Column(Integer)
    changed = Column(DateTime(timezone=True), default=dt_util.utcnow)

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.SchemaChanges("
            f"id={self.change_id}, schema_version={self.schema_version}, "
            f"changed='{self.changed.isoformat(sep=' ', timespec='seconds')}'"
            f")>"
        )


class StatisticsRuns(Base):  # type: ignore[misc,valid-type]
    """Representation of statistics run."""

    __tablename__ = TABLE_STATISTICS_RUNS
    run_id = Column(Integer, Identity(), primary_key=True)
    start = Column(DateTime(timezone=True), index=True)

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.StatisticsRuns("
            f"id={self.run_id}, start='{self.start.isoformat(sep=' ', timespec='seconds')}', "
            f")>"
        )


@overload
def process_timestamp(ts: None) -> None: ...


@overload
def process_timestamp(ts: datetime) -> datetime: ...


def process_timestamp(ts: datetime | None) -> datetime | None:
    """Process a timestamp into datetime object."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=dt_util.UTC)

    return dt_util.as_utc(ts)


@overload
def process_timestamp_to_utc_isoformat(ts: None) -> None: ...


@overload
def process_timestamp_to_utc_isoformat(ts: datetime) -> str: ...


def process_timestamp_to_utc_isoformat(ts: datetime | None) -> str | None:
    """Process a timestamp into UTC isotime."""
    if ts is None:
        return None
    if ts.tzinfo == dt_util.UTC:
        return ts.isoformat()
    if ts.tzinfo is None:
        return f"{ts.isoformat()}{DB_TIMEZONE}"
    return ts.astimezone(dt_util.UTC).isoformat()


class LazyState(State):
    """A lazy version of core State."""

    __slots__ = [
        "_row",
        "_attributes",
        "_last_changed",
        "_last_updated",
        "_context",
        "_attr_cache",
    ]

    def __init__(  # pylint: disable=super-init-not-called
        self, row: Row, attr_cache: dict[str, dict[str, Any]] | None = None
    ) -> None:
        """Init the lazy state."""
        self._row = row
        self.entity_id: str = self._row.entity_id
        self.state = self._row.state or ""
        self._attributes: dict[str, Any] | None = None
        self._last_changed: datetime | None = None
        self._last_updated: datetime | None = None
        self._context: Context | None = None
        self._attr_cache = attr_cache

    @property  # type: ignore[override]
    def attributes(self) -> dict[str, Any]:  # type: ignore[override]
        """State attributes."""
        if self._attributes is None:
            source = self._row.shared_attrs or self._row.attributes
            if self._attr_cache is not None and (
                attributes := self._attr_cache.get(source)
            ):
                self._attributes = attributes
                return attributes
            if source == EMPTY_JSON_OBJECT or source is None:
                self._attributes = {}
                return self._attributes
            try:
                self._attributes = json.loads(source)
            except ValueError:
                # When json.loads fails
                _LOGGER.exception(
                    "Error converting row to state attributes: %s", self._row
                )
                self._attributes = {}
            if self._attr_cache is not None:
                self._attr_cache[source] = self._attributes
        return self._attributes

    @attributes.setter
    def attributes(self, value: dict[str, Any]) -> None:
        """Set attributes."""
        self._attributes = value

    @property  # type: ignore[override]
    def context(self) -> Context:  # type: ignore[override]
        """State context."""
        if self._context is None:
            self._context = Context(id=None)  # type: ignore[arg-type]
        return self._context

    @context.setter
    def context(self, value: Context) -> None:
        """Set context."""
        self._context = value

    @property  # type: ignore[override]
    def last_changed(self) -> datetime:  # type: ignore[override]
        """Last changed datetime."""
        if self._last_changed is None:
            self._last_changed = process_timestamp(self._row.last_changed)
        return self._last_changed

    @last_changed.setter
    def last_changed(self, value: datetime) -> None:
        """Set last changed datetime."""
        self._last_changed = value

    @property  # type: ignore[override]
    def last_updated(self) -> datetime:  # type: ignore[override]
        """Last updated datetime."""
        if self._last_updated is None:
            if (last_updated := self._row.last_updated) is not None:
                self._last_updated = process_timestamp(last_updated)
            else:
                self._last_updated = self.last_changed
        return self._last_updated

    @last_updated.setter
    def last_updated(self, value: datetime) -> None:
        """Set last updated datetime."""
        self._last_updated = value

    def as_dict(self) -> dict[str, Any]:  # type: ignore[override]
        """Return a dict representation of the LazyState.

        Async friendly.

        To be used for JSON serialization.
        """
        if self._last_changed is None and self._last_updated is None:
            last_changed_isoformat = process_timestamp_to_utc_isoformat(
                self._row.last_changed
            )
            if (
                self._row.last_updated is None
                or self._row.last_changed == self._row.last_updated
            ):
                last_updated_isoformat = last_changed_isoformat
            else:
                last_updated_isoformat = process_timestamp_to_utc_isoformat(
                    self._row.last_updated
                )
        else:
            last_changed_isoformat = self.last_changed.isoformat()
            if self.last_changed == self.last_updated:
                last_updated_isoformat = last_changed_isoformat
            else:
                last_updated_isoformat = self.last_updated.isoformat()
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self._attributes or self.attributes,
            "last_changed": last_changed_isoformat,
            "last_updated": last_updated_isoformat,
        }

    def __eq__(self, other: object) -> bool:
        """Return the comparison."""
        return (
            other.__class__ in [self.__class__, State]
            and self.entity_id == other.entity_id
            and self.state == other.state
            and self.attributes == other.attributes
        )
