"""Models for Recorder."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import overload

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DB_TIMEZONE = "+00:00"

EMPTY_JSON_OBJECT = "{}"


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


def datetime_to_timestamp_or_none(dt: datetime | None) -> float | None:
    """Convert a datetime to a timestamp."""
    return None if dt is None else dt.timestamp()


def timestamp_to_datetime_or_none(ts: float | None) -> datetime | None:
    """Convert a timestamp to a datetime."""
    if not ts:
        return None
    return dt_util.utc_from_timestamp(ts)
