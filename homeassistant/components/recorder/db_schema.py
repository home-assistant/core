"""Models for SQLAlchemy."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from functools import lru_cache
import logging
import time
from typing import Any, cast

import ciso8601
from fnvhash import fnv1a_32
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    ColumnElement,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    distinct,
    type_coerce,
)
from sqlalchemy.dialects import mysql, oracle, postgresql, sqlite
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, aliased, mapped_column, relationship
from sqlalchemy.orm.query import RowReturningQuery
from sqlalchemy.orm.session import Session
from typing_extensions import Self

from homeassistant.const import (
    MAX_LENGTH_EVENT_CONTEXT_ID,
    MAX_LENGTH_EVENT_EVENT_TYPE,
    MAX_LENGTH_EVENT_ORIGIN,
    MAX_LENGTH_STATE_ENTITY_ID,
    MAX_LENGTH_STATE_STATE,
)
from homeassistant.core import Context, Event, EventOrigin, State, split_entity_id
from homeassistant.helpers.json import JSON_DUMP, json_bytes, json_bytes_strip_null
import homeassistant.util.dt as dt_util
from homeassistant.util.json import (
    JSON_DECODE_EXCEPTIONS,
    json_loads,
    json_loads_object,
)

from .const import ALL_DOMAIN_EXCLUDE_ATTRS, SupportedDialect
from .models import (
    StatisticData,
    StatisticDataTimestamp,
    StatisticMetaData,
    datetime_to_timestamp_or_none,
    process_timestamp,
)


# SQLAlchemy Schema
# pylint: disable=invalid-name
class Base(DeclarativeBase):
    """Base class for tables."""


SCHEMA_VERSION = 35

_LOGGER = logging.getLogger(__name__)

TABLE_EVENTS = "events"
TABLE_EVENT_DATA = "event_data"
TABLE_STATES = "states"
TABLE_STATE_ATTRIBUTES = "state_attributes"
TABLE_RECORDER_RUNS = "recorder_runs"
TABLE_SCHEMA_CHANGES = "schema_changes"
TABLE_STATISTICS = "statistics"
TABLE_STATISTICS_META = "statistics_meta"
TABLE_STATISTICS_RUNS = "statistics_runs"
TABLE_STATISTICS_SHORT_TERM = "statistics_short_term"

STATISTICS_TABLES = ("statistics", "statistics_short_term")

MAX_STATE_ATTRS_BYTES = 16384
PSQL_DIALECT = SupportedDialect.POSTGRESQL

ALL_TABLES = [
    TABLE_STATES,
    TABLE_STATE_ATTRIBUTES,
    TABLE_EVENTS,
    TABLE_EVENT_DATA,
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

LAST_UPDATED_INDEX_TS = "ix_states_last_updated_ts"
ENTITY_ID_LAST_UPDATED_INDEX_TS = "ix_states_entity_id_last_updated_ts"
EVENTS_CONTEXT_ID_INDEX = "ix_events_context_id"
STATES_CONTEXT_ID_INDEX = "ix_states_context_id"

_DEFAULT_TABLE_ARGS = {
    "mysql_default_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
    "mysql_engine": "InnoDB",
    "mariadb_default_charset": "utf8mb4",
    "mariadb_collate": "utf8mb4_unicode_ci",
    "mariadb_engine": "InnoDB",
}


class FAST_PYSQLITE_DATETIME(sqlite.DATETIME):
    """Use ciso8601 to parse datetimes instead of sqlalchemy built-in regex."""

    def result_processor(self, dialect, coltype):  # type: ignore[no-untyped-def]
        """Offload the datetime parsing to ciso8601."""
        return lambda value: None if value is None else ciso8601.parse_datetime(value)


JSON_VARIANT_CAST = Text().with_variant(
    postgresql.JSON(none_as_null=True), "postgresql"  # type: ignore[no-untyped-call]
)
JSONB_VARIANT_CAST = Text().with_variant(
    postgresql.JSONB(none_as_null=True), "postgresql"  # type: ignore[no-untyped-call]
)
DATETIME_TYPE = (
    DateTime(timezone=True)
    .with_variant(mysql.DATETIME(timezone=True, fsp=6), "mysql", "mariadb")  # type: ignore[no-untyped-call]
    .with_variant(FAST_PYSQLITE_DATETIME(), "sqlite")  # type: ignore[no-untyped-call]
)
DOUBLE_TYPE = (
    Float()
    .with_variant(mysql.DOUBLE(asdecimal=False), "mysql", "mariadb")  # type: ignore[no-untyped-call]
    .with_variant(oracle.DOUBLE_PRECISION(), "oracle")
    .with_variant(postgresql.DOUBLE_PRECISION(), "postgresql")
)

TIMESTAMP_TYPE = DOUBLE_TYPE


class JSONLiteral(JSON):
    """Teach SA how to literalize json."""

    def literal_processor(self, dialect: Dialect) -> Callable[[Any], str]:
        """Processor to convert a value to JSON."""

        def process(value: Any) -> str:
            """Dump json."""
            return JSON_DUMP(value)

        return process


EVENT_ORIGIN_ORDER = [EventOrigin.local, EventOrigin.remote]
EVENT_ORIGIN_TO_IDX = {origin: idx for idx, origin in enumerate(EVENT_ORIGIN_ORDER)}


class Events(Base):
    """Event history data."""

    __table_args__ = (
        # Used for fetching events at a specific time
        # see logbook
        Index("ix_events_event_type_time_fired_ts", "event_type", "time_fired_ts"),
        _DEFAULT_TABLE_ARGS,
    )
    __tablename__ = TABLE_EVENTS
    event_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    event_type: Mapped[str | None] = mapped_column(String(MAX_LENGTH_EVENT_EVENT_TYPE))
    event_data: Mapped[str | None] = mapped_column(
        Text().with_variant(mysql.LONGTEXT, "mysql", "mariadb")
    )
    origin: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_EVENT_ORIGIN)
    )  # no longer used for new rows
    origin_idx: Mapped[int | None] = mapped_column(SmallInteger)
    time_fired: Mapped[datetime | None] = mapped_column(
        DATETIME_TYPE
    )  # no longer used for new rows
    time_fired_ts: Mapped[float | None] = mapped_column(TIMESTAMP_TYPE, index=True)
    context_id: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_EVENT_CONTEXT_ID), index=True
    )
    context_user_id: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_EVENT_CONTEXT_ID)
    )
    context_parent_id: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_EVENT_CONTEXT_ID)
    )
    data_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("event_data.data_id"), index=True
    )
    event_data_rel: Mapped[EventData | None] = relationship("EventData")

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            "<recorder.Events("
            f"id={self.event_id}, type='{self.event_type}', "
            f"origin_idx='{self.origin_idx}', time_fired='{self._time_fired_isotime}'"
            f", data_id={self.data_id})>"
        )

    @property
    def _time_fired_isotime(self) -> str | None:
        """Return time_fired as an isotime string."""
        date_time: datetime | None
        if self.time_fired_ts is not None:
            date_time = dt_util.utc_from_timestamp(self.time_fired_ts)
        else:
            date_time = process_timestamp(self.time_fired)
        if date_time is None:
            return None
        return date_time.isoformat(sep=" ", timespec="seconds")

    @staticmethod
    def from_event(event: Event) -> Events:
        """Create an event database object from a native event."""
        return Events(
            event_type=event.event_type,
            event_data=None,
            origin_idx=EVENT_ORIGIN_TO_IDX.get(event.origin),
            time_fired=None,
            time_fired_ts=dt_util.utc_to_timestamp(event.time_fired),
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
                self.event_type or "",
                json_loads_object(self.event_data) if self.event_data else {},
                EventOrigin(self.origin)
                if self.origin
                else EVENT_ORIGIN_ORDER[self.origin_idx or 0],
                dt_util.utc_from_timestamp(self.time_fired_ts or 0),
                context=context,
            )
        except JSON_DECODE_EXCEPTIONS:
            # When json_loads fails
            _LOGGER.exception("Error converting to event: %s", self)
            return None


class EventData(Base):
    """Event data history."""

    __table_args__ = (_DEFAULT_TABLE_ARGS,)
    __tablename__ = TABLE_EVENT_DATA
    data_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    hash: Mapped[int | None] = mapped_column(BigInteger, index=True)
    # Note that this is not named attributes to avoid confusion with the states table
    shared_data: Mapped[str | None] = mapped_column(
        Text().with_variant(mysql.LONGTEXT, "mysql", "mariadb")
    )

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            "<recorder.EventData("
            f"id={self.data_id}, hash='{self.hash}', data='{self.shared_data}'"
            ")>"
        )

    @staticmethod
    def shared_data_bytes_from_event(
        event: Event, dialect: SupportedDialect | None
    ) -> bytes:
        """Create shared_data from an event."""
        if dialect == SupportedDialect.POSTGRESQL:
            return json_bytes_strip_null(event.data)
        return json_bytes(event.data)

    @staticmethod
    @lru_cache
    def hash_shared_data_bytes(shared_data_bytes: bytes) -> int:
        """Return the hash of json encoded shared data."""
        return cast(int, fnv1a_32(shared_data_bytes))

    def to_native(self) -> dict[str, Any]:
        """Convert to an event data dictionary."""
        shared_data = self.shared_data
        if shared_data is None:
            return {}
        try:
            return cast(dict[str, Any], json_loads(shared_data))
        except JSON_DECODE_EXCEPTIONS:
            _LOGGER.exception("Error converting row to event data: %s", self)
            return {}


class States(Base):
    """State change history."""

    __table_args__ = (
        # Used for fetching the state of entities at a specific time
        # (get_states in history.py)
        Index(ENTITY_ID_LAST_UPDATED_INDEX_TS, "entity_id", "last_updated_ts"),
        _DEFAULT_TABLE_ARGS,
    )
    __tablename__ = TABLE_STATES
    state_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    entity_id: Mapped[str | None] = mapped_column(String(MAX_LENGTH_STATE_ENTITY_ID))
    state: Mapped[str | None] = mapped_column(String(MAX_LENGTH_STATE_STATE))
    attributes: Mapped[str | None] = mapped_column(
        Text().with_variant(mysql.LONGTEXT, "mysql", "mariadb")
    )  # no longer used for new rows
    event_id: Mapped[int | None] = mapped_column(  # no longer used for new rows
        Integer, ForeignKey("events.event_id", ondelete="CASCADE"), index=True
    )
    last_changed: Mapped[datetime | None] = mapped_column(
        DATETIME_TYPE
    )  # no longer used for new rows
    last_changed_ts: Mapped[float | None] = mapped_column(TIMESTAMP_TYPE)
    last_updated: Mapped[datetime | None] = mapped_column(
        DATETIME_TYPE
    )  # no longer used for new rows
    last_updated_ts: Mapped[float | None] = mapped_column(
        TIMESTAMP_TYPE, default=time.time, index=True
    )
    old_state_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("states.state_id"), index=True
    )
    attributes_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("state_attributes.attributes_id"), index=True
    )
    context_id: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_EVENT_CONTEXT_ID), index=True
    )
    context_user_id: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_EVENT_CONTEXT_ID)
    )
    context_parent_id: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_EVENT_CONTEXT_ID)
    )
    origin_idx: Mapped[int | None] = mapped_column(
        SmallInteger
    )  # 0 is local, 1 is remote
    old_state: Mapped[States | None] = relationship("States", remote_side=[state_id])
    state_attributes: Mapped[StateAttributes | None] = relationship("StateAttributes")

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.States(id={self.state_id}, entity_id='{self.entity_id}',"
            f" state='{self.state}', event_id='{self.event_id}',"
            f" last_updated='{self._last_updated_isotime}',"
            f" old_state_id={self.old_state_id}, attributes_id={self.attributes_id})>"
        )

    @property
    def _last_updated_isotime(self) -> str | None:
        """Return last_updated as an isotime string."""
        date_time: datetime | None
        if self.last_updated_ts is not None:
            date_time = dt_util.utc_from_timestamp(self.last_updated_ts)
        else:
            date_time = process_timestamp(self.last_updated)
        if date_time is None:
            return None
        return date_time.isoformat(sep=" ", timespec="seconds")

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
            last_updated=None,
            last_changed=None,
        )
        # None state means the state was removed from the state machine
        if state is None:
            dbstate.state = ""
            dbstate.last_updated_ts = dt_util.utc_to_timestamp(event.time_fired)
            dbstate.last_changed_ts = None
            return dbstate

        dbstate.state = state.state
        dbstate.last_updated_ts = dt_util.utc_to_timestamp(state.last_updated)
        if state.last_updated == state.last_changed:
            dbstate.last_changed_ts = None
        else:
            dbstate.last_changed_ts = dt_util.utc_to_timestamp(state.last_changed)

        return dbstate

    def to_native(self, validate_entity_id: bool = True) -> State | None:
        """Convert to an HA state object."""
        context = Context(
            id=self.context_id,
            user_id=self.context_user_id,
            parent_id=self.context_parent_id,
        )
        try:
            attrs = json_loads_object(self.attributes) if self.attributes else {}
        except JSON_DECODE_EXCEPTIONS:
            # When json_loads fails
            _LOGGER.exception("Error converting row to state: %s", self)
            return None
        if self.last_changed_ts is None or self.last_changed_ts == self.last_updated_ts:
            last_changed = last_updated = dt_util.utc_from_timestamp(
                self.last_updated_ts or 0
            )
        else:
            last_updated = dt_util.utc_from_timestamp(self.last_updated_ts or 0)
            last_changed = dt_util.utc_from_timestamp(self.last_changed_ts or 0)
        return State(
            self.entity_id or "",
            self.state,  # type: ignore[arg-type]
            # Join the state_attributes table on attributes_id to get the attributes
            # for newer states
            attrs,
            last_changed,
            last_updated,
            context=context,
            validate_entity_id=validate_entity_id,
        )


class StateAttributes(Base):
    """State attribute change history."""

    __table_args__ = (_DEFAULT_TABLE_ARGS,)
    __tablename__ = TABLE_STATE_ATTRIBUTES
    attributes_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    hash: Mapped[int | None] = mapped_column(BigInteger, index=True)
    # Note that this is not named attributes to avoid confusion with the states table
    shared_attrs: Mapped[str | None] = mapped_column(
        Text().with_variant(mysql.LONGTEXT, "mysql", "mariadb")
    )

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.StateAttributes(id={self.attributes_id}, hash='{self.hash}',"
            f" attributes='{self.shared_attrs}')>"
        )

    @staticmethod
    def shared_attrs_bytes_from_event(
        event: Event,
        entity_sources: dict[str, dict[str, str]],
        exclude_attrs_by_domain: dict[str, set[str]],
        dialect: SupportedDialect | None,
    ) -> bytes:
        """Create shared_attrs from a state_changed event."""
        state: State | None = event.data.get("new_state")
        # None state means the state was removed from the state machine
        if state is None:
            return b"{}"
        domain = split_entity_id(state.entity_id)[0]
        exclude_attrs = set(ALL_DOMAIN_EXCLUDE_ATTRS)
        if base_platform_attrs := exclude_attrs_by_domain.get(domain):
            exclude_attrs |= base_platform_attrs
        if (entity_info := entity_sources.get(state.entity_id)) and (
            integration_attrs := exclude_attrs_by_domain.get(entity_info["domain"])
        ):
            exclude_attrs |= integration_attrs
        encoder = json_bytes_strip_null if dialect == PSQL_DIALECT else json_bytes
        bytes_result = encoder(
            {k: v for k, v in state.attributes.items() if k not in exclude_attrs}
        )
        if len(bytes_result) > MAX_STATE_ATTRS_BYTES:
            _LOGGER.warning(
                "State attributes for %s exceed maximum size of %s bytes. "
                "This can cause database performance issues; Attributes "
                "will not be stored",
                state.entity_id,
                MAX_STATE_ATTRS_BYTES,
            )
            return b"{}"
        return bytes_result

    @staticmethod
    @lru_cache(maxsize=2048)
    def hash_shared_attrs_bytes(shared_attrs_bytes: bytes) -> int:
        """Return the hash of json encoded shared attributes."""
        return cast(int, fnv1a_32(shared_attrs_bytes))

    def to_native(self) -> dict[str, Any]:
        """Convert to a state attributes dictionary."""
        shared_attrs = self.shared_attrs
        if shared_attrs is None:
            return {}
        try:
            return cast(dict[str, Any], json_loads(shared_attrs))
        except JSON_DECODE_EXCEPTIONS:
            # When json_loads fails
            _LOGGER.exception("Error converting row to state attributes: %s", self)
            return {}


class StatisticsBase:
    """Statistics base class."""

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    created: Mapped[datetime | None] = mapped_column(DATETIME_TYPE)  # No longer used
    created_ts: Mapped[float | None] = mapped_column(TIMESTAMP_TYPE, default=time.time)
    metadata_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(f"{TABLE_STATISTICS_META}.id", ondelete="CASCADE"),
        index=True,
    )
    start: Mapped[datetime | None] = mapped_column(
        DATETIME_TYPE, index=True
    )  # No longer used
    start_ts: Mapped[float | None] = mapped_column(TIMESTAMP_TYPE, index=True)
    mean: Mapped[float | None] = mapped_column(DOUBLE_TYPE)
    min: Mapped[float | None] = mapped_column(DOUBLE_TYPE)
    max: Mapped[float | None] = mapped_column(DOUBLE_TYPE)
    last_reset: Mapped[datetime | None] = mapped_column(DATETIME_TYPE)
    last_reset_ts: Mapped[float | None] = mapped_column(TIMESTAMP_TYPE)
    state: Mapped[float | None] = mapped_column(DOUBLE_TYPE)
    sum: Mapped[float | None] = mapped_column(DOUBLE_TYPE)

    duration: timedelta

    @classmethod
    def from_stats(cls, metadata_id: int, stats: StatisticData) -> Self:
        """Create object from a statistics with datatime objects."""
        return cls(  # type: ignore[call-arg]
            metadata_id=metadata_id,
            created=None,
            created_ts=time.time(),
            start=None,
            start_ts=dt_util.utc_to_timestamp(stats["start"]),
            mean=stats.get("mean"),
            min=stats.get("min"),
            max=stats.get("max"),
            last_reset=None,
            last_reset_ts=datetime_to_timestamp_or_none(stats.get("last_reset")),
            state=stats.get("state"),
            sum=stats.get("sum"),
        )

    @classmethod
    def from_stats_ts(cls, metadata_id: int, stats: StatisticDataTimestamp) -> Self:
        """Create object from a statistics with timestamps."""
        return cls(  # type: ignore[call-arg]
            metadata_id=metadata_id,
            created=None,
            created_ts=time.time(),
            start=None,
            start_ts=stats["start_ts"],
            mean=stats.get("mean"),
            min=stats.get("min"),
            max=stats.get("max"),
            last_reset=None,
            last_reset_ts=stats.get("last_reset_ts"),
            state=stats.get("state"),
            sum=stats.get("sum"),
        )


class Statistics(Base, StatisticsBase):
    """Long term statistics."""

    duration = timedelta(hours=1)

    __table_args__ = (
        # Used for fetching statistics for a certain entity at a specific time
        Index(
            "ix_statistics_statistic_id_start_ts",
            "metadata_id",
            "start_ts",
            unique=True,
        ),
    )
    __tablename__ = TABLE_STATISTICS


class StatisticsShortTerm(Base, StatisticsBase):
    """Short term statistics."""

    duration = timedelta(minutes=5)

    __table_args__ = (
        # Used for fetching statistics for a certain entity at a specific time
        Index(
            "ix_statistics_short_term_statistic_id_start_ts",
            "metadata_id",
            "start_ts",
            unique=True,
        ),
    )
    __tablename__ = TABLE_STATISTICS_SHORT_TERM


class StatisticsMeta(Base):
    """Statistics meta data."""

    __table_args__ = (_DEFAULT_TABLE_ARGS,)
    __tablename__ = TABLE_STATISTICS_META
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    statistic_id: Mapped[str | None] = mapped_column(
        String(255), index=True, unique=True
    )
    source: Mapped[str | None] = mapped_column(String(32))
    unit_of_measurement: Mapped[str | None] = mapped_column(String(255))
    has_mean: Mapped[bool | None] = mapped_column(Boolean)
    has_sum: Mapped[bool | None] = mapped_column(Boolean)
    name: Mapped[str | None] = mapped_column(String(255))

    @staticmethod
    def from_meta(meta: StatisticMetaData) -> StatisticsMeta:
        """Create object from meta data."""
        return StatisticsMeta(**meta)


class RecorderRuns(Base):
    """Representation of recorder run."""

    __table_args__ = (Index("ix_recorder_runs_start_end", "start", "end"),)
    __tablename__ = TABLE_RECORDER_RUNS
    run_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    start: Mapped[datetime] = mapped_column(DATETIME_TYPE, default=dt_util.utcnow)
    end: Mapped[datetime | None] = mapped_column(DATETIME_TYPE)
    closed_incorrect: Mapped[bool] = mapped_column(Boolean, default=False)
    created: Mapped[datetime] = mapped_column(DATETIME_TYPE, default=dt_util.utcnow)

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        end = (
            f"'{self.end.isoformat(sep=' ', timespec='seconds')}'" if self.end else None
        )
        return (
            f"<recorder.RecorderRuns(id={self.run_id},"
            f" start='{self.start.isoformat(sep=' ', timespec='seconds')}', end={end},"
            f" closed_incorrect={self.closed_incorrect},"
            f" created='{self.created.isoformat(sep=' ', timespec='seconds')}')>"
        )

    def entity_ids(self, point_in_time: datetime | None = None) -> list[str]:
        """Return the entity ids that existed in this run.

        Specify point_in_time if you want to know which existed at that point
        in time inside the run.
        """
        session = Session.object_session(self)

        assert session is not None, "RecorderRuns need to be persisted"

        query: RowReturningQuery[tuple[str]] = session.query(distinct(States.entity_id))

        query = query.filter(States.last_updated >= self.start)

        if point_in_time is not None:
            query = query.filter(States.last_updated < point_in_time)
        elif self.end is not None:
            query = query.filter(States.last_updated < self.end)

        return [row[0] for row in query]

    def to_native(self, validate_entity_id: bool = True) -> Self:
        """Return self, native format is this model."""
        return self


class SchemaChanges(Base):
    """Representation of schema version changes."""

    __tablename__ = TABLE_SCHEMA_CHANGES
    change_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    schema_version: Mapped[int | None] = mapped_column(Integer)
    changed: Mapped[datetime] = mapped_column(DATETIME_TYPE, default=dt_util.utcnow)

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            "<recorder.SchemaChanges("
            f"id={self.change_id}, schema_version={self.schema_version}, "
            f"changed='{self.changed.isoformat(sep=' ', timespec='seconds')}'"
            ")>"
        )


class StatisticsRuns(Base):
    """Representation of statistics run."""

    __tablename__ = TABLE_STATISTICS_RUNS
    run_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    start: Mapped[datetime] = mapped_column(DATETIME_TYPE, index=True)

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.StatisticsRuns(id={self.run_id},"
            f" start='{self.start.isoformat(sep=' ', timespec='seconds')}', )>"
        )


EVENT_DATA_JSON = type_coerce(
    EventData.shared_data.cast(JSONB_VARIANT_CAST), JSONLiteral(none_as_null=True)
)
OLD_FORMAT_EVENT_DATA_JSON = type_coerce(
    Events.event_data.cast(JSONB_VARIANT_CAST), JSONLiteral(none_as_null=True)
)

SHARED_ATTRS_JSON = type_coerce(
    StateAttributes.shared_attrs.cast(JSON_VARIANT_CAST), JSON(none_as_null=True)
)
OLD_FORMAT_ATTRS_JSON = type_coerce(
    States.attributes.cast(JSON_VARIANT_CAST), JSON(none_as_null=True)
)

ENTITY_ID_IN_EVENT: ColumnElement = EVENT_DATA_JSON["entity_id"]
OLD_ENTITY_ID_IN_EVENT: ColumnElement = OLD_FORMAT_EVENT_DATA_JSON["entity_id"]
DEVICE_ID_IN_EVENT: ColumnElement = EVENT_DATA_JSON["device_id"]
OLD_STATE = aliased(States, name="old_state")
