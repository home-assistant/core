"""Models for Recorder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Literal, TypedDict, overload

from awesomeversion import AwesomeVersion
from sqlalchemy.engine.row import Row

from homeassistant.const import (
    COMPRESSED_STATE_ATTRIBUTES,
    COMPRESSED_STATE_LAST_CHANGED,
    COMPRESSED_STATE_LAST_UPDATED,
    COMPRESSED_STATE_STATE,
)
from homeassistant.core import Context, State
import homeassistant.util.dt as dt_util
from homeassistant.util.json import json_loads_object

from .const import SupportedDialect

# pylint: disable=invalid-name

_LOGGER = logging.getLogger(__name__)

DB_TIMEZONE = "+00:00"

EMPTY_JSON_OBJECT = "{}"


class UnsupportedDialect(Exception):
    """The dialect or its version is not supported."""


class StatisticResult(TypedDict):
    """Statistic result data class.

    Allows multiple datapoints for the same statistic_id.
    """

    meta: StatisticMetaData
    stat: StatisticData


class StatisticDataTimestampBase(TypedDict):
    """Mandatory fields for statistic data class with a timestamp."""

    start_ts: float


class StatisticDataBase(TypedDict):
    """Mandatory fields for statistic data class."""

    start: datetime


class StatisticMixIn(TypedDict, total=False):
    """Mandatory fields for statistic data class."""

    state: float
    sum: float
    min: float
    max: float
    mean: float


class StatisticData(StatisticDataBase, StatisticMixIn, total=False):
    """Statistic data class."""

    last_reset: datetime | None


class StatisticDataTimestamp(StatisticDataTimestampBase, StatisticMixIn, total=False):
    """Statistic data class with a timestamp."""

    last_reset_ts: float | None


class StatisticMetaData(TypedDict):
    """Statistic meta data class."""

    has_mean: bool
    has_sum: bool
    name: str | None
    source: str
    statistic_id: str
    unit_of_measurement: str | None


@overload
def process_timestamp(ts: None) -> None:
    ...


@overload
def process_timestamp(ts: datetime) -> datetime:
    ...


def process_timestamp(ts: datetime | None) -> datetime | None:
    """Process a timestamp into datetime object."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=dt_util.UTC)

    return dt_util.as_utc(ts)


@overload
def process_timestamp_to_utc_isoformat(ts: None) -> None:
    ...


@overload
def process_timestamp_to_utc_isoformat(ts: datetime) -> str:
    ...


def process_timestamp_to_utc_isoformat(ts: datetime | None) -> str | None:
    """Process a timestamp into UTC isotime."""
    if ts is None:
        return None
    if ts.tzinfo == dt_util.UTC:
        return ts.isoformat()
    if ts.tzinfo is None:
        return f"{ts.isoformat()}{DB_TIMEZONE}"
    return ts.astimezone(dt_util.UTC).isoformat()


def process_datetime_to_timestamp(ts: datetime) -> float:
    """Process a datebase datetime to epoch.

    Mirrors the behavior of process_timestamp_to_utc_isoformat
    except it returns the epoch time.
    """
    if ts.tzinfo is None or ts.tzinfo == dt_util.UTC:
        return dt_util.utc_to_timestamp(ts)
    return ts.timestamp()


def datetime_to_timestamp_or_none(dt: datetime | None) -> float | None:
    """Convert a datetime to a timestamp."""
    if dt is None:
        return None
    return dt_util.utc_to_timestamp(dt)


def timestamp_to_datetime_or_none(ts: float | None) -> datetime | None:
    """Convert a timestamp to a datetime."""
    if not ts:
        return None
    return dt_util.utc_from_timestamp(ts)


class LazyStatePreSchema31(State):
    """A lazy version of core State before schema 31."""

    __slots__ = [
        "_row",
        "_attributes",
        "_last_changed",
        "_last_updated",
        "_context",
        "attr_cache",
    ]

    def __init__(  # pylint: disable=super-init-not-called
        self,
        row: Row,
        attr_cache: dict[str, dict[str, Any]],
        start_time: datetime | None,
    ) -> None:
        """Init the lazy state."""
        self._row = row
        self.entity_id: str = self._row.entity_id
        self.state = self._row.state or ""
        self._attributes: dict[str, Any] | None = None
        self._last_changed: datetime | None = start_time
        self._last_updated: datetime | None = start_time
        self._context: Context | None = None
        self.attr_cache = attr_cache

    @property  # type: ignore[override]
    def attributes(self) -> dict[str, Any]:
        """State attributes."""
        if self._attributes is None:
            self._attributes = decode_attributes_from_row(self._row, self.attr_cache)
        return self._attributes

    @attributes.setter
    def attributes(self, value: dict[str, Any]) -> None:
        """Set attributes."""
        self._attributes = value

    @property
    def context(self) -> Context:
        """State context."""
        if self._context is None:
            self._context = Context(id=None)
        return self._context

    @context.setter
    def context(self, value: Context) -> None:
        """Set context."""
        self._context = value

    @property
    def last_changed(self) -> datetime:
        """Last changed datetime."""
        if self._last_changed is None:
            if (last_changed := self._row.last_changed) is not None:
                self._last_changed = process_timestamp(last_changed)
            else:
                self._last_changed = self.last_updated
        return self._last_changed

    @last_changed.setter
    def last_changed(self, value: datetime) -> None:
        """Set last changed datetime."""
        self._last_changed = value

    @property
    def last_updated(self) -> datetime:
        """Last updated datetime."""
        if self._last_updated is None:
            self._last_updated = process_timestamp(self._row.last_updated)
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
            last_updated_isoformat = process_timestamp_to_utc_isoformat(
                self._row.last_updated
            )
            if (
                self._row.last_changed is None
                or self._row.last_changed == self._row.last_updated
            ):
                last_changed_isoformat = last_updated_isoformat
            else:
                last_changed_isoformat = process_timestamp_to_utc_isoformat(
                    self._row.last_changed
                )
        else:
            last_updated_isoformat = self.last_updated.isoformat()
            if self.last_changed == self.last_updated:
                last_changed_isoformat = last_updated_isoformat
            else:
                last_changed_isoformat = self.last_changed.isoformat()
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self._attributes or self.attributes,
            "last_changed": last_changed_isoformat,
            "last_updated": last_updated_isoformat,
        }


class LazyState(State):
    """A lazy version of core State after schema 31."""

    __slots__ = [
        "_row",
        "_attributes",
        "_last_changed_ts",
        "_last_updated_ts",
        "_context",
        "attr_cache",
    ]

    def __init__(  # pylint: disable=super-init-not-called
        self,
        row: Row,
        attr_cache: dict[str, dict[str, Any]],
        start_time: datetime | None,
    ) -> None:
        """Init the lazy state."""
        self._row = row
        self.entity_id: str = self._row.entity_id
        self.state = self._row.state or ""
        self._attributes: dict[str, Any] | None = None
        self._last_updated_ts: float | None = self._row.last_updated_ts or (
            dt_util.utc_to_timestamp(start_time) if start_time else None
        )
        self._last_changed_ts: float | None = (
            self._row.last_changed_ts or self._last_updated_ts
        )
        self._context: Context | None = None
        self.attr_cache = attr_cache

    @property  # type: ignore[override]
    def attributes(self) -> dict[str, Any]:
        """State attributes."""
        if self._attributes is None:
            self._attributes = decode_attributes_from_row(self._row, self.attr_cache)
        return self._attributes

    @attributes.setter
    def attributes(self, value: dict[str, Any]) -> None:
        """Set attributes."""
        self._attributes = value

    @property
    def context(self) -> Context:
        """State context."""
        if self._context is None:
            self._context = Context(id=None)
        return self._context

    @context.setter
    def context(self, value: Context) -> None:
        """Set context."""
        self._context = value

    @property
    def last_changed(self) -> datetime:
        """Last changed datetime."""
        assert self._last_changed_ts is not None
        return dt_util.utc_from_timestamp(self._last_changed_ts)

    @last_changed.setter
    def last_changed(self, value: datetime) -> None:
        """Set last changed datetime."""
        self._last_changed_ts = process_timestamp(value).timestamp()

    @property
    def last_updated(self) -> datetime:
        """Last updated datetime."""
        assert self._last_updated_ts is not None
        return dt_util.utc_from_timestamp(self._last_updated_ts)

    @last_updated.setter
    def last_updated(self, value: datetime) -> None:
        """Set last updated datetime."""
        self._last_updated_ts = process_timestamp(value).timestamp()

    def as_dict(self) -> dict[str, Any]:  # type: ignore[override]
        """Return a dict representation of the LazyState.

        Async friendly.

        To be used for JSON serialization.
        """
        last_updated_isoformat = self.last_updated.isoformat()
        if self._last_changed_ts == self._last_updated_ts:
            last_changed_isoformat = last_updated_isoformat
        else:
            last_changed_isoformat = self.last_changed.isoformat()
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self._attributes or self.attributes,
            "last_changed": last_changed_isoformat,
            "last_updated": last_updated_isoformat,
        }


def decode_attributes_from_row(
    row: Row, attr_cache: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Decode attributes from a database row."""
    source: str = row.shared_attrs or row.attributes
    if (attributes := attr_cache.get(source)) is not None:
        return attributes
    if not source or source == EMPTY_JSON_OBJECT:
        return {}
    try:
        attr_cache[source] = attributes = json_loads_object(source)
    except ValueError:
        _LOGGER.exception("Error converting row to state attributes: %s", source)
        attr_cache[source] = attributes = {}
    return attributes


def row_to_compressed_state(
    row: Row,
    attr_cache: dict[str, dict[str, Any]],
    start_time: datetime | None,
) -> dict[str, Any]:
    """Convert a database row to a compressed state schema 31 and later."""
    comp_state = {
        COMPRESSED_STATE_STATE: row.state,
        COMPRESSED_STATE_ATTRIBUTES: decode_attributes_from_row(row, attr_cache),
    }
    if start_time:
        comp_state[COMPRESSED_STATE_LAST_UPDATED] = dt_util.utc_to_timestamp(start_time)
    else:
        row_last_updated_ts: float = row.last_updated_ts
        comp_state[COMPRESSED_STATE_LAST_UPDATED] = row_last_updated_ts
        if (
            row_changed_changed_ts := row.last_changed_ts
        ) and row_last_updated_ts != row_changed_changed_ts:
            comp_state[COMPRESSED_STATE_LAST_CHANGED] = row_changed_changed_ts
    return comp_state


def row_to_compressed_state_pre_schema_31(
    row: Row,
    attr_cache: dict[str, dict[str, Any]],
    start_time: datetime | None,
) -> dict[str, Any]:
    """Convert a database row to a compressed state before schema 31."""
    comp_state = {
        COMPRESSED_STATE_STATE: row.state,
        COMPRESSED_STATE_ATTRIBUTES: decode_attributes_from_row(row, attr_cache),
    }
    if start_time:
        comp_state[COMPRESSED_STATE_LAST_UPDATED] = start_time.timestamp()
    else:
        row_last_updated: datetime = row.last_updated
        comp_state[COMPRESSED_STATE_LAST_UPDATED] = process_datetime_to_timestamp(
            row_last_updated
        )
        if (
            row_changed_changed := row.last_changed
        ) and row_last_updated != row_changed_changed:
            comp_state[COMPRESSED_STATE_LAST_CHANGED] = process_datetime_to_timestamp(
                row_changed_changed
            )
    return comp_state


class CalendarStatisticPeriod(TypedDict, total=False):
    """Statistic period definition."""

    period: Literal["hour", "day", "week", "month", "year"]
    offset: int


class FixedStatisticPeriod(TypedDict, total=False):
    """Statistic period definition."""

    end_time: datetime
    start_time: datetime


class RollingWindowStatisticPeriod(TypedDict, total=False):
    """Statistic period definition."""

    duration: timedelta
    offset: timedelta


class StatisticPeriod(TypedDict, total=False):
    """Statistic period definition."""

    calendar: CalendarStatisticPeriod
    fixed_period: FixedStatisticPeriod
    rolling_window: RollingWindowStatisticPeriod


@dataclass
class DatabaseEngine:
    """Properties of the database engine."""

    dialect: SupportedDialect
    optimizer: DatabaseOptimizer
    version: AwesomeVersion | None


@dataclass
class DatabaseOptimizer:
    """Properties of the database optimizer for the configured database engine."""

    # Some MariaDB versions have a bug that causes a slow query when using
    # a range in a select statement with an IN clause.
    #
    # https://jira.mariadb.org/browse/MDEV-25020
    #
    slow_range_in_select: bool
