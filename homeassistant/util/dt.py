"""Provides helper methods to handle the time in HA."""
import datetime as dt
import re

import pytz

DATE_STR_FORMAT = "%Y-%m-%d"
UTC = DEFAULT_TIME_ZONE = pytz.utc


# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
# https://github.com/django/django/blob/master/LICENSE
DATETIME_RE = re.compile(
    r'(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})'
    r'[T ](?P<hour>\d{1,2}):(?P<minute>\d{1,2})'
    r'(?::(?P<second>\d{1,2})(?:\.(?P<microsecond>\d{1,6})\d{0,6})?)?'
    r'(?P<tzinfo>Z|[+-]\d{2}(?::?\d{2})?)?$'
)


def set_default_time_zone(time_zone):
    """Set a default time zone to be used when none is specified."""
    global DEFAULT_TIME_ZONE  # pylint: disable=global-statement

    assert isinstance(time_zone, dt.tzinfo)

    DEFAULT_TIME_ZONE = time_zone


def get_time_zone(time_zone_str):
    """Get time zone from string. Return None if unable to determine."""
    try:
        return pytz.timezone(time_zone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        return None


def utcnow():
    """Get now in UTC time."""
    return dt.datetime.now(UTC)


def now(time_zone=None):
    """Get now in specified time zone."""
    return dt.datetime.now(time_zone or DEFAULT_TIME_ZONE)


def as_utc(dattim):
    """Return a datetime as UTC time.

    Assumes datetime without tzinfo to be in the DEFAULT_TIME_ZONE.
    """
    if dattim.tzinfo == UTC:
        return dattim
    elif dattim.tzinfo is None:
        dattim = DEFAULT_TIME_ZONE.localize(dattim)

    return dattim.astimezone(UTC)


def as_timestamp(dt_value):
    """Convert a date/time into a unix time (seconds since 1970)."""
    if hasattr(dt_value, "timestamp"):
        parsed_dt = dt_value
    else:
        parsed_dt = parse_datetime(str(dt_value))
        if not parsed_dt:
            raise ValueError("not a valid date/time.")
    return parsed_dt.timestamp()


def as_local(dattim):
    """Convert a UTC datetime object to local time zone."""
    if dattim.tzinfo == DEFAULT_TIME_ZONE:
        return dattim
    elif dattim.tzinfo is None:
        dattim = UTC.localize(dattim)

    return dattim.astimezone(DEFAULT_TIME_ZONE)


def utc_from_timestamp(timestamp):
    """Return a UTC time from a timestamp."""
    return dt.datetime.utcfromtimestamp(timestamp).replace(tzinfo=UTC)


def start_of_local_day(dt_or_d=None):
    """Return local datetime object of start of day from date or datetime."""
    if dt_or_d is None:
        dt_or_d = now().date()
    elif isinstance(dt_or_d, dt.datetime):
        dt_or_d = dt_or_d.date()

    return dt.datetime.combine(dt_or_d, dt.time()).replace(
        tzinfo=DEFAULT_TIME_ZONE)


# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
# https://github.com/django/django/blob/master/LICENSE
def parse_datetime(dt_str):
    """Parse a string and return a datetime.datetime.

    This function supports time zone offsets. When the input contains one,
    the output uses a timezone with a fixed offset from UTC.
    Raises ValueError if the input is well formatted but not a valid datetime.
    Returns None if the input isn't well formatted.
    """
    match = DATETIME_RE.match(dt_str)
    if not match:
        return None
    kws = match.groupdict()
    if kws['microsecond']:
        kws['microsecond'] = kws['microsecond'].ljust(6, '0')
    tzinfo = kws.pop('tzinfo')
    if tzinfo == 'Z':
        tzinfo = UTC
    elif tzinfo is not None:
        offset_mins = int(tzinfo[-2:]) if len(tzinfo) > 3 else 0
        offset_hours = int(tzinfo[1:3])
        offset = dt.timedelta(hours=offset_hours, minutes=offset_mins)
        if tzinfo[0] == '-':
            offset = -offset
        tzinfo = dt.timezone(offset)
    kws = {k: int(v) for k, v in kws.items() if v is not None}
    kws['tzinfo'] = tzinfo
    return dt.datetime(**kws)


def parse_date(dt_str):
    """Convert a date string to a date object."""
    try:
        return dt.datetime.strptime(dt_str, DATE_STR_FORMAT).date()
    except ValueError:  # If dt_str did not match our format
        return None


def parse_time(time_str):
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
def get_age(date):
    # pylint: disable=too-many-return-statements
    """
    Take a datetime and return its "age" as a string.

    The age can be in second, minute, hour, day, month or year. Only the
    biggest unit is considered, e.g. if it's 2 days and 3 hours, "2 days" will
    be returned.
    Make sure date is not in the future, or else it won't work.
    """
    def formatn(number, unit):
        """Add "unit" if it's plural."""
        if number == 1:
            return "1 %s" % unit
        elif number > 1:
            return "%d %ss" % (number, unit)

    def q_n_r(first, second):
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
    if second > 0:
        return formatn(second, 'second')

    return "0 second"
