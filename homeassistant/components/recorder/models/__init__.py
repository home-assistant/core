"""Models for Recorder."""
from __future__ import annotations

from .context import (
    bytes_to_ulid_or_none,
    bytes_to_uuid_hex_or_none,
    ulid_to_bytes_or_none,
    uuid_hex_to_bytes_or_none,
)
from .database import DatabaseEngine, DatabaseOptimizer, UnsupportedDialect
from .event import extract_event_type_ids
from .state import LazyState, extract_metadata_ids, row_to_compressed_state
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
    "CalendarStatisticPeriod",
    "DatabaseEngine",
    "DatabaseOptimizer",
    "FixedStatisticPeriod",
    "LazyState",
    "RollingWindowStatisticPeriod",
    "StatisticData",
    "StatisticDataTimestamp",
    "StatisticMetaData",
    "StatisticPeriod",
    "StatisticResult",
    "UnsupportedDialect",
    "bytes_to_ulid_or_none",
    "bytes_to_uuid_hex_or_none",
    "datetime_to_timestamp_or_none",
    "extract_event_type_ids",
    "extract_metadata_ids",
    "process_datetime_to_timestamp",
    "process_timestamp",
    "process_timestamp_to_utc_isoformat",
    "row_to_compressed_state",
    "timestamp_to_datetime_or_none",
    "ulid_to_bytes_or_none",
    "uuid_hex_to_bytes_or_none",
]
