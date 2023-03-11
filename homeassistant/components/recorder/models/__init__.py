"""Models for Recorder."""
from __future__ import annotations

from .context import (
    bytes_to_ulid_or_none,
    bytes_to_uuid_hex_or_none,
    ulid_to_bytes_or_none,
    uuid_hex_to_bytes_or_none,
)
from .database import DatabaseEngine, DatabaseOptimizer, UnsupportedDialect
from .state import LazyState, row_to_compressed_state
from .statistics import (
    CalendarStatisticPeriod,
    FixedStatisticPeriod,
    RollingWindowStatisticPeriod,
    StatisticData,
    StatisticDataTimestamp,
    StatisticMetaData,
    StatisticPeriod,
    StatisticResult,
)
from .time import (
    datetime_to_timestamp_or_none,
    process_datetime_to_timestamp,
    process_timestamp,
    process_timestamp_to_utc_isoformat,
    timestamp_to_datetime_or_none,
)

__all__ = [
    "process_timestamp",
    "process_timestamp_to_utc_isoformat",
    "process_datetime_to_timestamp",
    "datetime_to_timestamp_or_none",
    "timestamp_to_datetime_or_none",
    "StatisticData",
    "StatisticMetaData",
    "StatisticResult",
    "StatisticDataTimestamp",
    "CalendarStatisticPeriod",
    "FixedStatisticPeriod",
    "RollingWindowStatisticPeriod",
    "StatisticPeriod",
    "ulid_to_bytes_or_none",
    "bytes_to_ulid_or_none",
    "uuid_hex_to_bytes_or_none",
    "bytes_to_uuid_hex_or_none",
    "DatabaseEngine",
    "DatabaseOptimizer",
    "UnsupportedDialect",
    "LazyState",
    "row_to_compressed_state",
]
