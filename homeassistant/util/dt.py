"""Helper methods to handle the time in Home Assistant."""
import datetime as dt
import re
from typing import (Any, Union, Optional,  # noqa pylint: disable=unused-import
                    Tuple, List, cast, Dict)

import pytz
import pytz.exceptions as pytzexceptions
import pytz.tzinfo as pytzinfo  # noqa pylint: disable=unused-import

from homeassistant.const import MATCH_ALL

DATE_STR_FORMAT = "%Y-%m-%d"
UTC = pytz.utc
DEFAULT_TIME_ZONE = pytz.utc  # type: dt.tzinfo


# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
# https://github.com/django/django/blob/master/LICENSE
DATETIME_RE = re.compile(
    r'(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})'
    r'[T ](?P<hour>\d{1,2}):(?P<minute>\d{1,2})'
    r'(?::(?P<second>\d{1,2})(?:\.(?P<microsecond>\d{1,6})\d{0,6})?)?'
    r'(?P<tzinfo>Z|[+-]\d{2}(?::?\d{2})?)?$'
)


def set_default_time_zone(time_zone: dt.tzinfo) -> None:
    """Set a default time zone to be used when none is specified.

    Async friendly.
    """
    global DEFAULT_TIME_ZONE

    # NOTE: Remove in the future in favour of typing
    assert isinstance(time_zone, dt.tzinfo)

    DEFAULT_TIME_ZONE = time_zone


def get_time_zone(time_zone_str: str) -> Optional[dt.tzinfo]:
    """Get time zone from string. Return None if unable to determine.

    Async friendly.
    """
    try:
        return pytz.timezone(time_zone_str)
    except pytzexceptions.UnknownTimeZoneError:
        return None


def utcnow() -> dt.datetime:
    """Get now in UTC time."""
    return dt.datetime.now(UTC)


def now(time_zone: Optional[dt.tzinfo] = None) -> dt.datetime:
    """Get now in specified time zone."""
    return dt.datetime.now(time_zone or DEFAULT_TIME_ZONE)


def as_utc(dattim: dt.datetime) -> dt.datetime:
    """Return a datetime as UTC time.

    Assumes datetime without tzinfo to be in the DEFAULT_TIME_ZONE.
    """
    if dattim.tzinfo == UTC:
        return dattim
    if dattim.tzinfo is None:
        dattim = DEFAULT_TIME_ZONE.localize(dattim)  # type: ignore

    return dattim.astimezone(UTC)


def as_timestamp(dt_value: dt.datetime) -> float:
    """Convert a date/time into a unix time (seconds since 1970)."""
    if hasattr(dt_value, "timestamp"):
        parsed_dt = dt_value  # type: Optional[dt.datetime]
    else:
        parsed_dt = parse_datetime(str(dt_value))
    if parsed_dt is None:
        raise ValueError("not a valid date/time.")
    return parsed_dt.timestamp()


def as_local(dattim: dt.datetime) -> dt.datetime:
    """Convert a UTC datetime object to local time zone."""
    if dattim.tzinfo == DEFAULT_TIME_ZONE:
        return dattim
    if dattim.tzinfo is None:
        dattim = UTC.localize(dattim)

    return dattim.astimezone(DEFAULT_TIME_ZONE)


def utc_from_timestamp(timestamp: float) -> dt.datetime:
    """Return a UTC time from a timestamp."""
    return UTC.localize(dt.datetime.utcfromtimestamp(timestamp))


def start_of_local_day(
        dt_or_d: Union[dt.date, dt.datetime, None] = None) -> dt.datetime:
    """Return local datetime object of start of day from date or datetime."""
    if dt_or_d is None:
        date = now().date()  # type: dt.date
    elif isinstance(dt_or_d, dt.datetime):
        date = dt_or_d.date()
    return DEFAULT_TIME_ZONE.localize(dt.datetime.combine(  # type: ignore
        date, dt.time()))


# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
# https://github.com/django/django/blob/master/LICENSE
def parse_datetime(dt_str: str) -> Optional[dt.datetime]:
    """Parse a string and return a datetime.datetime.

    This function supports time zone offsets. When the input contains one,
    the output uses a timezone with a fixed offset from UTC.
    Raises ValueError if the input is well formatted but not a valid datetime.
    Returns None if the input isn't well formatted.
    """
    match = DATETIME_RE.match(dt_str)
    if not match:
        return None
    kws = match.groupdict()  # type: Dict[str, Any]
    if kws['microsecond']:
        kws['microsecond'] = kws['microsecond'].ljust(6, '0')
    tzinfo_str = kws.pop('tzinfo')

    tzinfo = None  # type: Optional[dt.tzinfo]
    if tzinfo_str == 'Z':
        tzinfo = UTC
    elif tzinfo_str is not None:
        offset_mins = int(tzinfo_str[-2:]) if len(tzinfo_str) > 3 else 0
        offset_hours = int(tzinfo_str[1:3])
        offset = dt.timedelta(hours=offset_hours, minutes=offset_mins)
        if tzinfo_str[0] == '-':
            offset = -offset
        tzinfo = dt.timezone(offset)
    kws = {k: int(v) for k, v in kws.items() if v is not None}
    kws['tzinfo'] = tzinfo
    return dt.datetime(**kws)


def parse_date(dt_str: str) -> Optional[dt.date]:
    """Convert a date string to a date object."""
    try:
        return dt.datetime.strptime(dt_str, DATE_STR_FORMAT).date()
    except ValueError:  # If dt_str did not match our format
        return None


def parse_time(time_str: str) -> Optional[dt.time]:
    """Parse a time string (00:20:00) into Time object.

    Return None if invalid.
    """
    parts = str(time_str).split(':')
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        return dt.time(hour, minute, second)
    except ValueError:
        # ValueError if value cannot be converted to an int or not in range
        return None


# Found in this gist: https://gist.github.com/zhangsen/1199964
def get_age(date: dt.datetime) -> str:
    """
    Take a datetime and return its "age" as a string.

    The age can be in second, minute, hour, day, month or year. Only the
    biggest unit is considered, e.g. if it's 2 days and 3 hours, "2 days" will
    be returned.
    Make sure date is not in the future, or else it won't work.
    """
    def formatn(number: int, unit: str) -> str:
        """Add "unit" if it's plural."""
        if number == 1:
            return '1 {}'.format(unit)
        return '{:d} {}s'.format(number, unit)

    def q_n_r(first: int, second: int) -> Tuple[int, int]:
        """Return quotient and remaining."""
        return first // second, first % second

    delta = now() - date
    day = delta.days
    second = delta.seconds

    year, day = q_n_r(day, 365)
    if year > 0:
        return formatn(year, 'year')

    month, day = q_n_r(day, 30)
    if month > 0:
        return formatn(month, 'month')
    if day > 0:
        return formatn(day, 'day')

    hour, second = q_n_r(second, 3600)
    if hour > 0:
        return formatn(hour, 'hour')

    minute, second = q_n_r(second, 60)
    if minute > 0:
        return formatn(minute, 'minute')

    return formatn(second, 'second')


def parse_time_expression(parameter: Any, min_value: int, max_value: int) \
        -> List[int]:
    """Parse the time expression part and return a list of times to match."""
    if parameter is None or parameter == MATCH_ALL:
        res = [x for x in range(min_value, max_value + 1)]
    elif isinstance(parameter, str) and parameter.startswith('/'):
        parameter = float(parameter[1:])
        res = [x for x in range(min_value, max_value + 1)
               if x % parameter == 0]
    elif not hasattr(parameter, '__iter__'):
        res = [int(parameter)]
    else:
        res = list(sorted(int(x) for x in parameter))

    for val in res:
        if val < min_value or val > max_value:
            raise ValueError(
                "Time expression '{}': parameter {} out of range ({} to {})"
                "".format(parameter, val, min_value, max_value)
            )

    return res


# pylint: disable=redefined-outer-name
def find_next_time_expression_time(now: dt.datetime,
                                   seconds: List[int], minutes: List[int],
                                   hours: List[int]) -> dt.datetime:
    """Find the next datetime from now for which the time expression matches.

    The algorithm looks at each time unit separately and tries to find the
    next one that matches for each. If any of them would roll over, all
    time units below that are reset to the first matching value.

    Timezones are also handled (the tzinfo of the now object is used),
    including daylight saving time.
    """
    if not seconds or not minutes or not hours:
        raise ValueError("Cannot find a next time: Time expression never "
                         "matches!")

    def _lower_bound(arr: List[int], cmp: int) -> Optional[int]:
        """Return the first value in arr greater or equal to cmp.

        Return None if no such value exists.
        """
        left = 0
        right = len(arr)
        while left < right:
            mid = (left + right) // 2
            if arr[mid] < cmp:
                left = mid + 1
            else:
                right = mid

        if left == len(arr):
            return None
        return arr[left]

    result = now.replace(microsecond=0)

    # Match next second
    next_second = _lower_bound(seconds, result.second)
    if next_second is None:
        # No second to match in this minute. Roll-over to next minute.
        next_second = seconds[0]
        result += dt.timedelta(minutes=1)

    result = result.replace(second=next_second)

    # Match next minute
    next_minute = _lower_bound(minutes, result.minute)
    if next_minute != result.minute:
        # We're in the next minute. Seconds needs to be reset.
        result = result.replace(second=seconds[0])

    if next_minute is None:
        # No minute to match in this hour. Roll-over to next hour.
        next_minute = minutes[0]
        result += dt.timedelta(hours=1)

    result = result.replace(minute=next_minute)

    # Match next hour
    next_hour = _lower_bound(hours, result.hour)
    if next_hour != result.hour:
        # We're in the next hour. Seconds+minutes needs to be reset.
        result.replace(second=seconds[0], minute=minutes[0])

    if next_hour is None:
        # No minute to match in this day. Roll-over to next day.
        next_hour = hours[0]
        result += dt.timedelta(days=1)

    result = result.replace(hour=next_hour)

    if result.tzinfo is None:
        return result

    # Now we need to handle timezones. We will make this datetime object
    # "naive" first and then re-convert it to the target timezone.
    # This is so that we can call pytz's localize and handle DST changes.
    tzinfo = result.tzinfo  # type: pytzinfo.DstTzInfo
    result = result.replace(tzinfo=None)

    try:
        result = tzinfo.localize(result, is_dst=None)
    except pytzexceptions.AmbiguousTimeError:
        # This happens when we're leaving daylight saving time and local
        # clocks are rolled back. In this case, we want to trigger
        # on both the DST and non-DST time. So when "now" is in the DST
        # use the DST-on time, and if not, use the DST-off time.
        use_dst = bool(now.dst())
        result = tzinfo.localize(result, is_dst=use_dst)
    except pytzexceptions.NonExistentTimeError:
        # This happens when we're entering daylight saving time and local
        # clocks are rolled forward, thus there are local times that do
        # not exist. In this case, we want to trigger on the next time
        # that *does* exist.
        # In the worst case, this will run through all the seconds in the
        # time shift, but that's max 3600 operations for once per year
        result = result.replace(tzinfo=tzinfo) + dt.timedelta(seconds=1)
        return find_next_time_expression_time(result, seconds, minutes, hours)

    result_dst = cast(dt.timedelta, result.dst())
    now_dst = cast(dt.timedelta, now.dst())
    if result_dst >= now_dst:
        return result

    # Another edge-case when leaving DST:
    # When now is in DST and ambiguous *and* the next trigger time we *should*
    # trigger is ambiguous and outside DST, the excepts above won't catch it.
    # For example: if triggering on 2:30 and now is 28.10.2018 2:30 (in DST)
    # we should trigger next on 28.10.2018 2:30 (out of DST), but our
    # algorithm above would produce 29.10.2018 2:30 (out of DST)

    # Step 1: Check if now is ambiguous
    try:
        tzinfo.localize(now.replace(tzinfo=None), is_dst=None)
        return result
    except pytzexceptions.AmbiguousTimeError:
        pass

    # Step 2: Check if result of (now - DST) is ambiguous.
    check = now - now_dst
    check_result = find_next_time_expression_time(
        check, seconds, minutes, hours)
    try:
        tzinfo.localize(check_result.replace(tzinfo=None), is_dst=None)
        return result
    except pytzexceptions.AmbiguousTimeError:
        pass

    # OK, edge case does apply. We must override the DST to DST-off
    check_result = tzinfo.localize(check_result.replace(tzinfo=None),
                                   is_dst=False)
    return check_result
