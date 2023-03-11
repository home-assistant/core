"""Models for Recorder."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
import logging
from typing import Any, Literal, TypedDict
from uuid import UUID

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
from homeassistant.util.ulid import bytes_to_ulid, ulid_to_bytes

from ..const import SupportedDialect
from .state_attributes import decode_attributes_from_row
from .time import (
    datetime_to_timestamp_or_none,
    process_datetime_to_timestamp,
    process_timestamp,
    process_timestamp_to_utc_isoformat,
    timestamp_to_datetime_or_none,
)

# pylint: disable=invalid-name

_LOGGER = logging.getLogger(__name__)

DB_TIMEZONE = "+00:00"


__all__ = [
    "process_timestamp",
    "process_timestamp_to_utc_isoformat",
    "process_datetime_to_timestamp",
    "datetime_to_timestamp_or_none",
    "timestamp_to_datetime_or_none",
]


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


def ulid_to_bytes_or_none(ulid: str | None) -> bytes | None:
    """Convert an ulid to bytes."""
    if ulid is None:
        return None
    return ulid_to_bytes(ulid)


def bytes_to_ulid_or_none(_bytes: bytes | None) -> str | None:
    """Convert bytes to a ulid."""
    if _bytes is None:
        return None
    return bytes_to_ulid(_bytes)


@lru_cache(maxsize=16)
def uuid_hex_to_bytes_or_none(uuid_hex: str | None) -> bytes | None:
    """Convert a uuid hex to bytes."""
    if uuid_hex is None:
        return None
    with suppress(ValueError):
        return UUID(hex=uuid_hex).bytes
    return None


@lru_cache(maxsize=16)
def bytes_to_uuid_hex_or_none(_bytes: bytes | None) -> str | None:
    """Convert bytes to a uuid hex."""
    if _bytes is None:
        return None
    with suppress(ValueError):
        return UUID(bytes=_bytes).hex
    return None


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
