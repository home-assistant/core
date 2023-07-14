"""Models for Recorder."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import overload

import homeassistant.util.dt as dt_util

# pylint: disable=invalid-name

_LOGGER = logging.getLogger(__name__)

DB_TIMEZONE = "+00:00"

EMPTY_JSON_OBJECT = "{}"


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
