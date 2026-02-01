"""DateTime functions for Home Assistant templates."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.template.helpers import raise_no_default
from homeassistant.helpers.template.render_info import render_info_cv
from homeassistant.util import dt as dt_util

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment

_SENTINEL = object()
DATE_STR_FORMAT = "%Y-%m-%d %H:%M:%S"


class DateTimeExtension(BaseTemplateExtension):
    """Extension for datetime-related template functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the datetime extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "as_datetime",
                    self.as_datetime,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "as_local",
                    self.as_local,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "as_timedelta",
                    self.as_timedelta,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "as_timestamp",
                    self.as_timestamp,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "strptime",
                    self.strptime,
                    as_global=True,
                ),
                TemplateFunction(
                    "timedelta",
                    timedelta,
                    as_global=True,
                ),
                TemplateFunction(
                    "timestamp_custom",
                    self.timestamp_custom,
                    as_filter=True,
                ),
                TemplateFunction(
                    "timestamp_local",
                    self.timestamp_local,
                    as_filter=True,
                ),
                TemplateFunction(
                    "timestamp_utc",
                    self.timestamp_utc,
                    as_filter=True,
                ),
                TemplateFunction(
                    "datetime",
                    self.is_datetime,
                    as_test=True,
                ),
                # Functions that require hass
                TemplateFunction(
                    "now",
                    self.now,
                    as_global=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "utcnow",
                    self.utcnow,
                    as_global=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "relative_time",
                    self.relative_time,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "time_since",
                    self.time_since,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "time_until",
                    self.time_until,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "today_at",
                    self.today_at,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
            ],
        )

    def timestamp_custom(
        self,
        value: Any,
        date_format: str = DATE_STR_FORMAT,
        local: bool = True,
        default: Any = _SENTINEL,
    ) -> Any:
        """Filter to convert given timestamp to format."""
        try:
            result = dt_util.utc_from_timestamp(value)

            if local:
                result = dt_util.as_local(result)

            return result.strftime(date_format)
        except (ValueError, TypeError):
            # If timestamp can't be converted
            if default is _SENTINEL:
                raise_no_default("timestamp_custom", value)
            return default

    def timestamp_local(self, value: Any, default: Any = _SENTINEL) -> Any:
        """Filter to convert given timestamp to local date/time."""
        try:
            return dt_util.as_local(dt_util.utc_from_timestamp(value)).isoformat()
        except (ValueError, TypeError):
            # If timestamp can't be converted
            if default is _SENTINEL:
                raise_no_default("timestamp_local", value)
            return default

    def timestamp_utc(self, value: Any, default: Any = _SENTINEL) -> Any:
        """Filter to convert given timestamp to UTC date/time."""
        try:
            return dt_util.utc_from_timestamp(value).isoformat()
        except (ValueError, TypeError):
            # If timestamp can't be converted
            if default is _SENTINEL:
                raise_no_default("timestamp_utc", value)
            return default

    def as_timestamp(self, value: Any, default: Any = _SENTINEL) -> Any:
        """Filter and function which tries to convert value to timestamp."""
        try:
            return dt_util.as_timestamp(value)
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("as_timestamp", value)
            return default

    def as_datetime(self, value: Any, default: Any = _SENTINEL) -> Any:
        """Filter to convert a time string or UNIX timestamp to datetime object."""
        # Return datetime.datetime object without changes
        if type(value) is datetime:
            return value
        # Add midnight to datetime.date object
        if type(value) is date:
            return datetime.combine(value, time(0, 0, 0))
        try:
            # Check for a valid UNIX timestamp string, int or float
            timestamp = float(value)
            return dt_util.utc_from_timestamp(timestamp)
        except (ValueError, TypeError):
            # Try to parse datetime string to datetime object
            try:
                return dt_util.parse_datetime(value, raise_on_error=True)
            except (ValueError, TypeError):
                if default is _SENTINEL:
                    # Return None on string input
                    # to ensure backwards compatibility with HA Core 2024.1 and before.
                    if isinstance(value, str):
                        return None
                    raise_no_default("as_datetime", value)
                return default

    def as_timedelta(self, value: str) -> timedelta | None:
        """Parse a ISO8601 duration like 'PT10M' to a timedelta."""
        return dt_util.parse_duration(value)

    def strptime(self, string: str, fmt: str, default: Any = _SENTINEL) -> Any:
        """Parse a time string to datetime."""
        try:
            return datetime.strptime(string, fmt)
        except (ValueError, AttributeError, TypeError):
            if default is _SENTINEL:
                raise_no_default("strptime", string)
            return default

    def as_local(self, value: datetime) -> datetime:
        """Filter and function to convert time to local."""
        return dt_util.as_local(value)

    def is_datetime(self, value: Any) -> bool:
        """Return whether a value is a datetime."""
        return isinstance(value, datetime)

    def now(self) -> datetime:
        """Record fetching now."""
        if (render_info := render_info_cv.get()) is not None:
            render_info.has_time = True

        return dt_util.now()

    def utcnow(self) -> datetime:
        """Record fetching utcnow."""
        if (render_info := render_info_cv.get()) is not None:
            render_info.has_time = True

        return dt_util.utcnow()

    def today_at(self, time_str: str = "") -> datetime:
        """Record fetching now where the time has been replaced with value."""
        if (render_info := render_info_cv.get()) is not None:
            render_info.has_time = True

        today = dt_util.start_of_local_day()
        if not time_str:
            return today

        if (time_today := dt_util.parse_time(time_str)) is None:
            raise ValueError(
                f"could not convert {type(time_str).__name__} to datetime: '{time_str}'"
            )

        return datetime.combine(today, time_today, today.tzinfo)

    def relative_time(self, value: Any) -> Any:
        """Take a datetime and return its "age" as a string.

        The age can be in second, minute, hour, day, month or year. Only the
        biggest unit is considered, e.g. if it's 2 days and 3 hours, "2 days" will
        be returned.
        If the input datetime is in the future,
        the input datetime will be returned.

        If the input are not a datetime object the input will be returned unmodified.

        Note: This template function is deprecated in favor of `time_until`, but is still
        supported so as not to break old templates.
        """
        if (render_info := render_info_cv.get()) is not None:
            render_info.has_time = True

        if not isinstance(value, datetime):
            return value
        if not value.tzinfo:
            value = dt_util.as_local(value)
        if dt_util.now() < value:
            return value
        return dt_util.get_age(value)

    def time_since(self, value: Any | datetime, precision: int = 1) -> Any:
        """Take a datetime and return its "age" as a string.

        The age can be in seconds, minutes, hours, days, months and year.

        precision is the number of units to return, with the last unit rounded.

        If the value not a datetime object the input will be returned unmodified.
        """
        if (render_info := render_info_cv.get()) is not None:
            render_info.has_time = True

        if not isinstance(value, datetime):
            return value
        if not value.tzinfo:
            value = dt_util.as_local(value)
        if dt_util.now() < value:
            return value

        return dt_util.get_age(value, precision)

    def time_until(self, value: Any | datetime, precision: int = 1) -> Any:
        """Take a datetime and return the amount of time until that time as a string.

        The time until can be in seconds, minutes, hours, days, months and years.

        precision is the number of units to return, with the last unit rounded.

        If the value not a datetime object the input will be returned unmodified.
        """
        if (render_info := render_info_cv.get()) is not None:
            render_info.has_time = True

        if not isinstance(value, datetime):
            return value
        if not value.tzinfo:
            value = dt_util.as_local(value)
        if dt_util.now() > value:
            return value

        return dt_util.get_time_remaining(value, precision)
