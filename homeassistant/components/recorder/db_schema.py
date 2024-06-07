"""Models for SQLAlchemy."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import time
from typing import Any, Self, cast

import ciso8601
from fnv_hash_fast import fnv1a_32
from sqlalchemy import (
    CHAR,
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
    LargeBinary,
    SmallInteger,
    String,
    Text,
    case,
    type_coerce,
)
from sqlalchemy.dialects import mysql, oracle, postgresql, sqlite
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, aliased, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from homeassistant.const import (
    MAX_LENGTH_EVENT_EVENT_TYPE,
    MAX_LENGTH_STATE_ENTITY_ID,
    MAX_LENGTH_STATE_STATE,
)
from homeassistant.core import Context, Event, EventOrigin, EventStateChangedData, State
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
    bytes_to_ulid_or_none,
    bytes_to_uuid_hex_or_none,
    datetime_to_timestamp_or_none,
    process_timestamp,
    ulid_to_bytes_or_none,
    uuid_hex_to_bytes_or_none,
)


# SQLAlchemy Schema
class Base(DeclarativeBase):
    """Base class for tables."""


SCHEMA_VERSION = 43

_LOGGER = logging.getLogger(__name__)

TABLE_EVENTS = "events"
TABLE_EVENT_DATA = "event_data"
TABLE_EVENT_TYPES = "event_types"
TABLE_STATES = "states"
TABLE_STATE_ATTRIBUTES = "state_attributes"
TABLE_STATES_META = "states_meta"
TABLE_RECORDER_RUNS = "recorder_runs"
TABLE_SCHEMA_CHANGES = "schema_changes"
TABLE_STATISTICS = "statistics"
TABLE_STATISTICS_META = "statistics_meta"
TABLE_STATISTICS_RUNS = "statistics_runs"
TABLE_STATISTICS_SHORT_TERM = "statistics_short_term"
TABLE_MIGRATION_CHANGES = "migration_changes"

STATISTICS_TABLES = ("statistics", "statistics_short_term")

MAX_STATE_ATTRS_BYTES = 16384
MAX_EVENT_DATA_BYTES = 32768

PSQL_DIALECT = SupportedDialect.POSTGRESQL

ALL_TABLES = [
    TABLE_STATES,
    TABLE_STATE_ATTRIBUTES,
    TABLE_EVENTS,
    TABLE_EVENT_DATA,
    TABLE_EVENT_TYPES,
    TABLE_RECORDER_RUNS,
    TABLE_SCHEMA_CHANGES,
    TABLE_MIGRATION_CHANGES,
    TABLE_STATES_META,
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
METADATA_ID_LAST_UPDATED_INDEX_TS = "ix_states_metadata_id_last_updated_ts"
EVENTS_CONTEXT_ID_BIN_INDEX = "ix_events_context_id_bin"
STATES_CONTEXT_ID_BIN_INDEX = "ix_states_context_id_bin"
LEGACY_STATES_EVENT_ID_INDEX = "ix_states_event_id"
LEGACY_STATES_ENTITY_ID_LAST_UPDATED_INDEX = "ix_states_entity_id_last_updated_ts"
CONTEXT_ID_BIN_MAX_LENGTH = 16

MYSQL_COLLATE = "utf8mb4_unicode_ci"
MYSQL_DEFAULT_CHARSET = "utf8mb4"
MYSQL_ENGINE = "InnoDB"

_DEFAULT_TABLE_ARGS = {
    "mysql_default_charset": MYSQL_DEFAULT_CHARSET,
    "mysql_collate": MYSQL_COLLATE,
    "mysql_engine": MYSQL_ENGINE,
    "mariadb_default_charset": MYSQL_DEFAULT_CHARSET,
    "mariadb_collate": MYSQL_COLLATE,
    "mariadb_engine": MYSQL_ENGINE,
}


class UnusedDateTime(DateTime):
    """An unused column type that behaves like a datetime."""


class Unused(CHAR):
    """An unused column type that behaves like a string."""


@compiles(UnusedDateTime, "mysql", "mariadb", "sqlite")  # type: ignore[misc,no-untyped-call]
@compiles(Unused, "mysql", "mariadb", "sqlite")  # type: ignore[misc,no-untyped-call]
def compile_char_zero(type_: TypeDecorator, compiler: Any, **kw: Any) -> str:
    """Compile UnusedDateTime and Unused as CHAR(0) on mysql, mariadb, and sqlite."""
    return "CHAR(0)"  # Uses 1 byte on MySQL (no change on sqlite)


@compiles(Unused, "postgresql")  # type: ignore[misc,no-untyped-call]
def compile_char_one(type_: TypeDecorator, compiler: Any, **kw: Any) -> str:
    """Compile Unused as CHAR(1) on postgresql."""
    return "CHAR(1)"  # Uses 1 byte


class FAST_PYSQLITE_DATETIME(sqlite.DATETIME):
    """Use ciso8601 to parse datetimes instead of sqlalchemy built-in regex."""

    def result_processor(self, dialect, coltype):  # type: ignore[no-untyped-def]
        """Offload the datetime parsing to ciso8601."""
        return lambda value: None if value is None else ciso8601.parse_datetime(value)


class NativeLargeBinary(LargeBinary):
    """A faster version of LargeBinary for engines that support python bytes natively."""

    def result_processor(self, dialect, coltype):  # type: ignore[no-untyped-def]
        """No conversion needed for engines that support native bytes."""
        return None


# For MariaDB and MySQL we can use an unsigned integer type since it will fit 2**32
# for sqlite and postgresql we use a bigint
UINT_32_TYPE = BigInteger().with_variant(
    mysql.INTEGER(unsigned=True),  # type: ignore[no-untyped-call]
    "mysql",
    "mariadb",
)
JSON_VARIANT_CAST = Text().with_variant(
    postgresql.JSON(none_as_null=True),  # type: ignore[no-untyped-call]
    "postgresql",
)
JSONB_VARIANT_CAST = Text().with_variant(
    postgresql.JSONB(none_as_null=True),  # type: ignore[no-untyped-call]
    "postgresql",
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
UNUSED_LEGACY_COLUMN = Unused(0)
UNUSED_LEGACY_DATETIME_COLUMN = UnusedDateTime(timezone=True)
UNUSED_LEGACY_INTEGER_COLUMN = SmallInteger()
DOUBLE_PRECISION_TYPE_SQL = "DOUBLE PRECISION"
CONTEXT_BINARY_TYPE = LargeBinary(CONTEXT_ID_BIN_MAX_LENGTH).with_variant(
    NativeLargeBinary(CONTEXT_ID_BIN_MAX_LENGTH), "mysql", "mariadb", "sqlite"
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
        Index(
            "ix_events_event_type_id_time_fired_ts", "event_type_id", "time_fired_ts"
        ),
        Index(
            EVENTS_CONTEXT_ID_BIN_INDEX,
            "context_id_bin",
            mysql_length=CONTEXT_ID_BIN_MAX_LENGTH,
            mariadb_length=CONTEXT_ID_BIN_MAX_LENGTH,
        ),
        _DEFAULT_TABLE_ARGS,
    )
    __tablename__ = TABLE_EVENTS
    event_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    event_type: Mapped[str | None] = mapped_column(UNUSED_LEGACY_COLUMN)
    event_data: Mapped[str | None] = mapped_column(UNUSED_LEGACY_COLUMN)
    origin: Mapped[str | None] = mapped_column(UNUSED_LEGACY_COLUMN)
    origin_idx: Mapped[int | None] = mapped_column(SmallInteger)
    time_fired: Mapped[datetime | None] = mapped_column(UNUSED_LEGACY_DATETIME_COLUMN)
    time_fired_ts: Mapped[float | None] = mapped_column(TIMESTAMP_TYPE, index=True)
    context_id: Mapped[str | None] = mapped_column(UNUSED_LEGACY_COLUMN)
    context_user_id: Mapped[str | None] = mapped_column(UNUSED_LEGACY_COLUMN)
    context_parent_id: Mapped[str | None] = mapped_column(UNUSED_LEGACY_COLUMN)
    data_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("event_data.data_id"), index=True
    )
    context_id_bin: Mapped[bytes | None] = mapped_column(CONTEXT_BINARY_TYPE)
    context_user_id_bin: Mapped[bytes | None] = mapped_column(CONTEXT_BINARY_TYPE)
    context_parent_id_bin: Mapped[bytes | None] = mapped_column(CONTEXT_BINARY_TYPE)
    event_type_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("event_types.event_type_id")
    )
    event_data_rel: Mapped[EventData | None] = relationship("EventData")
    event_type_rel: Mapped[EventTypes | None] = relationship("EventTypes")

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            "<recorder.Events("
            f"id={self.event_id}, event_type_id='{self.event_type_id}', "
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
            event_type=None,
            event_data=None,
            origin_idx=EVENT_ORIGIN_TO_IDX.get(event.origin),
            time_fired=None,
            time_fired_ts=event.time_fired_timestamp,
            context_id=None,
            context_id_bin=ulid_to_bytes_or_none(event.context.id),
            context_user_id=None,
            context_user_id_bin=uuid_hex_to_bytes_or_none(event.context.user_id),
            context_parent_id=None,
            context_parent_id_bin=ulid_to_bytes_or_none(event.context.parent_id),
        )

    def to_native(self, validate_entity_id: bool = True) -> Event | None:
        """Convert to a native HA Event."""
        context = Context(
            id=bytes_to_ulid_or_none(self.context_id_bin),
            user_id=bytes_to_uuid_hex_or_none(self.context_user_id_bin),
            parent_id=bytes_to_ulid_or_none(self.context_parent_id_bin),
        )
        try:
            return Event(
                self.event_type or "",
                json_loads_object(self.event_data) if self.event_data else {},
                EventOrigin(self.origin)
                if self.origin
                else EVENT_ORIGIN_ORDER[self.origin_idx or 0],
                self.time_fired_ts or 0,
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
    hash: Mapped[int | None] = mapped_column(UINT_32_TYPE, index=True)
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
            bytes_result = json_bytes_strip_null(event.data)
        bytes_result = json_bytes(event.data)
        if len(bytes_result) > MAX_EVENT_DATA_BYTES:
            _LOGGER.warning(
                "Event data for %s exceed maximum size of %s bytes. "
                "This can cause database performance issues; Event data "
                "will not be stored",
                event.event_type,
                MAX_EVENT_DATA_BYTES,
            )
            return b"{}"
        return bytes_result

    @staticmethod
    def hash_shared_data_bytes(shared_data_bytes: bytes) -> int:
        """Return the hash of json encoded shared data."""
        return fnv1a_32(shared_data_bytes)

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


class EventTypes(Base):
    """Event type history."""

    __table_args__ = (_DEFAULT_TABLE_ARGS,)
    __tablename__ = TABLE_EVENT_TYPES
    event_type_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    event_type: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_EVENT_EVENT_TYPE), index=True, unique=True
    )

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            "<recorder.EventTypes("
            f"id={self.event_type_id}, event_type='{self.event_type}'"
            ")>"
        )


class States(Base):
    """State change history."""

    __table_args__ = (
        # Used for fetching the state of entities at a specific time
        # (get_states in history.py)
        Index(METADATA_ID_LAST_UPDATED_INDEX_TS, "metadata_id", "last_updated_ts"),
        Index(
            STATES_CONTEXT_ID_BIN_INDEX,
            "context_id_bin",
            mysql_length=CONTEXT_ID_BIN_MAX_LENGTH,
            mariadb_length=CONTEXT_ID_BIN_MAX_LENGTH,
        ),
        _DEFAULT_TABLE_ARGS,
    )
    __tablename__ = TABLE_STATES
    state_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    entity_id: Mapped[str | None] = mapped_column(UNUSED_LEGACY_COLUMN)
    state: Mapped[str | None] = mapped_column(String(MAX_LENGTH_STATE_STATE))
    attributes: Mapped[str | None] = mapped_column(UNUSED_LEGACY_COLUMN)
    event_id: Mapped[int | None] = mapped_column(UNUSED_LEGACY_INTEGER_COLUMN)
    last_changed: Mapped[datetime | None] = mapped_column(UNUSED_LEGACY_DATETIME_COLUMN)
    last_changed_ts: Mapped[float | None] = mapped_column(TIMESTAMP_TYPE)
    last_reported_ts: Mapped[float | None] = mapped_column(TIMESTAMP_TYPE)
    last_updated: Mapped[datetime | None] = mapped_column(UNUSED_LEGACY_DATETIME_COLUMN)
    last_updated_ts: Mapped[float | None] = mapped_column(
        TIMESTAMP_TYPE, default=time.time, index=True
    )
    old_state_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("states.state_id"), index=True
    )
    attributes_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("state_attributes.attributes_id"), index=True
    )
    context_id: Mapped[str | None] = mapped_column(UNUSED_LEGACY_COLUMN)
    context_user_id: Mapped[str | None] = mapped_column(UNUSED_LEGACY_COLUMN)
    context_parent_id: Mapped[str | None] = mapped_column(UNUSED_LEGACY_COLUMN)
    origin_idx: Mapped[int | None] = mapped_column(
        SmallInteger
    )  # 0 is local, 1 is remote
    old_state: Mapped[States | None] = relationship("States", remote_side=[state_id])
    state_attributes: Mapped[StateAttributes | None] = relationship("StateAttributes")
    context_id_bin: Mapped[bytes | None] = mapped_column(CONTEXT_BINARY_TYPE)
    context_user_id_bin: Mapped[bytes | None] = mapped_column(CONTEXT_BINARY_TYPE)
    context_parent_id_bin: Mapped[bytes | None] = mapped_column(CONTEXT_BINARY_TYPE)
    metadata_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("states_meta.metadata_id")
    )
    states_meta_rel: Mapped[StatesMeta | None] = relationship("StatesMeta")

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.States(id={self.state_id}, entity_id='{self.entity_id}'"
            f" metadata_id={self.metadata_id},"
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
    def from_event(event: Event[EventStateChangedData]) -> States:
        """Create object from a state_changed event."""
        entity_id = event.data["entity_id"]
        state = event.data["new_state"]
        dbstate = States(
            entity_id=entity_id,
            attributes=None,
            context_id=None,
            context_id_bin=ulid_to_bytes_or_none(event.context.id),
            context_user_id=None,
            context_user_id_bin=uuid_hex_to_bytes_or_none(event.context.user_id),
            context_parent_id=None,
            context_parent_id_bin=ulid_to_bytes_or_none(event.context.parent_id),
            origin_idx=EVENT_ORIGIN_TO_IDX.get(event.origin),
            last_updated=None,
            last_changed=None,
        )
        # None state means the state was removed from the state machine
        if state is None:
            dbstate.state = ""
            dbstate.last_updated_ts = event.time_fired_timestamp
            dbstate.last_changed_ts = None
            dbstate.last_reported_ts = None
            return dbstate

        dbstate.state = state.state
        dbstate.last_updated_ts = state.last_updated_timestamp
        if state.last_updated == state.last_changed:
            dbstate.last_changed_ts = None
        else:
            dbstate.last_changed_ts = state.last_changed_timestamp
        if state.last_updated == state.last_reported:
            dbstate.last_reported_ts = None
        else:
            dbstate.last_reported_ts = state.last_reported_timestamp

        return dbstate

    def to_native(self, validate_entity_id: bool = True) -> State | None:
        """Convert to an HA state object."""
        context = Context(
            id=bytes_to_ulid_or_none(self.context_id_bin),
            user_id=bytes_to_uuid_hex_or_none(self.context_user_id_bin),
            parent_id=bytes_to_ulid_or_none(self.context_parent_id_bin),
        )
        try:
            attrs = json_loads_object(self.attributes) if self.attributes else {}
        except JSON_DECODE_EXCEPTIONS:
            # When json_loads fails
            _LOGGER.exception("Error converting row to state: %s", self)
            return None
        last_updated = dt_util.utc_from_timestamp(self.last_updated_ts or 0)
        if self.last_changed_ts is None or self.last_changed_ts == self.last_updated_ts:
            last_changed = dt_util.utc_from_timestamp(self.last_updated_ts or 0)
        else:
            last_changed = dt_util.utc_from_timestamp(self.last_changed_ts or 0)
        if (
            self.last_reported_ts is None
            or self.last_reported_ts == self.last_updated_ts
        ):
            last_reported = dt_util.utc_from_timestamp(self.last_updated_ts or 0)
        else:
            last_reported = dt_util.utc_from_timestamp(self.last_reported_ts or 0)
        return State(
            self.entity_id or "",
            self.state,  # type: ignore[arg-type]
            # Join the state_attributes table on attributes_id to get the attributes
            # for newer states
            attrs,
            last_changed=last_changed,
            last_reported=last_reported,
            last_updated=last_updated,
            context=context,
            validate_entity_id=validate_entity_id,
        )


class StateAttributes(Base):
    """State attribute change history."""

    __table_args__ = (_DEFAULT_TABLE_ARGS,)
    __tablename__ = TABLE_STATE_ATTRIBUTES
    attributes_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    hash: Mapped[int | None] = mapped_column(UINT_32_TYPE, index=True)
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
        event: Event[EventStateChangedData],
        dialect: SupportedDialect | None,
    ) -> bytes:
        """Create shared_attrs from a state_changed event."""
        # None state means the state was removed from the state machine
        if (state := event.data["new_state"]) is None:
            return b"{}"
        if state_info := state.state_info:
            exclude_attrs = {
                *ALL_DOMAIN_EXCLUDE_ATTRS,
                *state_info["unrecorded_attributes"],
            }
        else:
            exclude_attrs = ALL_DOMAIN_EXCLUDE_ATTRS
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
    def hash_shared_attrs_bytes(shared_attrs_bytes: bytes) -> int:
        """Return the hash of json encoded shared attributes."""
        return fnv1a_32(shared_attrs_bytes)

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


class StatesMeta(Base):
    """Metadata for states."""

    __table_args__ = (_DEFAULT_TABLE_ARGS,)
    __tablename__ = TABLE_STATES_META
    metadata_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    entity_id: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_STATE_ENTITY_ID), index=True, unique=True
    )

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            "<recorder.StatesMeta("
            f"id={self.metadata_id}, entity_id='{self.entity_id}'"
            ")>"
        )


class StatisticsBase:
    """Statistics base class."""

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    created: Mapped[datetime | None] = mapped_column(UNUSED_LEGACY_DATETIME_COLUMN)
    created_ts: Mapped[float | None] = mapped_column(TIMESTAMP_TYPE, default=time.time)
    metadata_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(f"{TABLE_STATISTICS_META}.id", ondelete="CASCADE"),
    )
    start: Mapped[datetime | None] = mapped_column(UNUSED_LEGACY_DATETIME_COLUMN)
    start_ts: Mapped[float | None] = mapped_column(TIMESTAMP_TYPE, index=True)
    mean: Mapped[float | None] = mapped_column(DOUBLE_TYPE)
    min: Mapped[float | None] = mapped_column(DOUBLE_TYPE)
    max: Mapped[float | None] = mapped_column(DOUBLE_TYPE)
    last_reset: Mapped[datetime | None] = mapped_column(UNUSED_LEGACY_DATETIME_COLUMN)
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
        _DEFAULT_TABLE_ARGS,
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
        _DEFAULT_TABLE_ARGS,
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

    __table_args__ = (
        Index("ix_recorder_runs_start_end", "start", "end"),
        _DEFAULT_TABLE_ARGS,
    )
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

    def to_native(self, validate_entity_id: bool = True) -> Self:
        """Return self, native format is this model."""
        return self


class MigrationChanges(Base):
    """Representation of migration changes."""

    __tablename__ = TABLE_MIGRATION_CHANGES
    __table_args__ = (_DEFAULT_TABLE_ARGS,)

    migration_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    version: Mapped[int] = mapped_column(SmallInteger)


class SchemaChanges(Base):
    """Representation of schema version changes."""

    __tablename__ = TABLE_SCHEMA_CHANGES
    __table_args__ = (_DEFAULT_TABLE_ARGS,)

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
    __table_args__ = (_DEFAULT_TABLE_ARGS,)

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

SHARED_ATTR_OR_LEGACY_ATTRIBUTES = case(
    (StateAttributes.shared_attrs.is_(None), States.attributes),
    else_=StateAttributes.shared_attrs,
).label("attributes")
SHARED_DATA_OR_LEGACY_EVENT_DATA = case(
    (EventData.shared_data.is_(None), Events.event_data), else_=EventData.shared_data
).label("event_data")
