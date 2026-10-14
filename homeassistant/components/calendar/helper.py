"""Helper functions for the calendar integration."""

from collections.abc import Callable, Iterable
import datetime
from itertools import groupby
from typing import Any

from dateutil.rrule import rrulestr
import probatio

from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import LIST_EVENT_FIELDS

# Don't support rrules more often than daily
VALID_FREQS = {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}


# Ensure events created in Home Assistant have a positive duration
MIN_NEW_EVENT_DURATION = datetime.timedelta(seconds=1)


# Events must have a non-negative duration e.g. Google Calendar can create zero
# duration events in the UI.
MIN_EVENT_DURATION = datetime.timedelta(seconds=0)


def has_timezone(*keys: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Assert that all datetime values have a timezone."""

    def validate(obj: dict[str, Any]) -> dict[str, Any]:
        """Validate that all datetime values have a timezone."""
        for k in keys:
            if (
                (value := obj.get(k))
                and isinstance(value, datetime.datetime)
                and value.tzinfo is None
            ):
                raise probatio.Invalid("Expected all values to have a timezone")
        return obj

    return validate


def has_consistent_timezone(*keys: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Verify that all datetime values have a consistent timezone."""

    def validate(obj: dict[str, Any]) -> dict[str, Any]:
        """Test that all keys that are datetime values have the same timezone."""
        tzinfos = []
        for key in keys:
            if not (value := obj.get(key)) or not isinstance(value, datetime.datetime):
                return obj
            tzinfos.append(value.tzinfo)
        uniq_values = groupby(tzinfos)
        if len(list(uniq_values)) > 1:
            raise probatio.Invalid("Expected all values to have the same timezone")
        return obj

    return validate


def as_local_timezone(*keys: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Convert all datetime values to the local timezone."""

    def validate(obj: dict[str, Any]) -> dict[str, Any]:
        """Convert all keys that are datetime values to local timezone."""
        for k in keys:
            if (value := obj.get(k)) and isinstance(value, datetime.datetime):
                obj[k] = dt_util.as_local(value)
        return obj

    return validate


def has_min_duration(
    start_key: str, end_key: str, min_duration: datetime.timedelta
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Verify that the time span between start and end has a minimum duration."""

    def validate(obj: dict[str, Any]) -> dict[str, Any]:
        if (start := obj.get(start_key)) and (end := obj.get(end_key)):
            duration = end - start
            if duration < min_duration:
                raise probatio.Invalid(
                    "Expected minimum event duration"
                    f" of {min_duration} ({start}, {end})"
                )
        return obj

    return validate


def has_positive_interval(
    start_key: str, end_key: str, duration_key: str
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Verify that the time span between start and end is greater than zero."""

    def validate(obj: dict[str, Any]) -> dict[str, Any]:
        if (duration := obj.get(duration_key)) is not None:
            if duration <= datetime.timedelta(seconds=0):
                raise probatio.Invalid(f"Expected positive duration ({duration})")
            return obj

        if (start := obj.get(start_key)) and (end := obj.get(end_key)):
            if start >= end:
                raise probatio.Invalid(
                    f"Expected end time to be after start time ({start}, {end})"
                )
        return obj

    return validate


def has_same_type(*keys: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Verify that all values are of the same type."""

    def validate(obj: dict[str, Any]) -> dict[str, Any]:
        """Test that all keys in the dict have values of the same type."""
        uniq_values = groupby(type(obj[k]) for k in keys)
        if len(list(uniq_values)) > 1:
            raise probatio.Invalid(f"Expected all values to be the same type: {keys}")
        return obj

    return validate


def validate_rrule(value: Any) -> str:
    """Validate a recurrence rule string."""
    if value is None:
        raise probatio.Invalid("rrule value is None")

    if not isinstance(value, str):
        raise probatio.Invalid("rrule value expected a string")

    try:
        rrulestr(value)
    except ValueError as err:
        raise probatio.Invalid(f"Invalid rrule '{value}': {err}") from err

    # Example format: FREQ=DAILY;UNTIL=...
    rule_parts = dict(s.split("=", 1) for s in value.split(";"))
    if not (freq := rule_parts.get("FREQ")):
        raise probatio.Invalid("rrule did not contain FREQ")

    if freq not in VALID_FREQS:
        raise probatio.Invalid(f"Invalid frequency for rule: {value}")

    return str(value)


def empty_as_none(value: str | None) -> str | None:
    """Convert any empty string values to None."""
    return value or None


def event_dict_factory(obj: Iterable[tuple[str, Any]]) -> dict[str, str]:
    """Convert CalendarEvent dataclass items to dictionary of attributes."""
    result: dict[str, str] = {}
    for name, value in obj:
        if isinstance(value, (datetime.datetime, datetime.date)):
            result[name] = value.isoformat()
        elif value is not None:
            result[name] = str(value)
    return result


def api_event_dict_factory(obj: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    """Convert CalendarEvent dataclass items to the API format."""
    result: dict[str, Any] = {}
    for name, value in obj:
        if isinstance(value, datetime.datetime):
            result[name] = {"dateTime": dt_util.as_local(value).isoformat()}
        elif isinstance(value, datetime.date):
            result[name] = {"date": value.isoformat()}
        else:
            result[name] = value
    return result


def list_events_dict_factory(
    obj: Iterable[tuple[str, Any]],
) -> dict[str, JsonValueType]:
    """Convert CalendarEvent dataclass items to dictionary of attributes."""
    return {
        name: value
        for name, value in event_dict_factory(obj).items()
        if name in LIST_EVENT_FIELDS and value is not None
    }


def get_datetime_local(
    dt_or_d: datetime.datetime | datetime.date,
) -> datetime.datetime:
    """Convert a calendar event date/datetime to a datetime if needed."""
    if isinstance(dt_or_d, datetime.datetime):
        return dt_util.as_local(dt_or_d)
    return dt_util.start_of_local_day(dt_or_d)


def _get_api_date(dt_or_d: datetime.datetime | datetime.date) -> dict[str, str]:
    """Convert a calendar event date/datetime to a datetime if needed."""
    if isinstance(dt_or_d, datetime.datetime):
        return {"dateTime": dt_util.as_local(dt_or_d).isoformat()}
    return {"date": dt_or_d.isoformat()}
