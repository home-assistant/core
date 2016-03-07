"""Provides helper methods to handle the time in HA."""
import datetime as dt

import pytz

DATETIME_STR_FORMAT = "%H:%M:%S %d-%m-%Y"
DATE_STR_FORMAT = "%Y-%m-%d"
TIME_STR_FORMAT = "%H:%M"
UTC = DEFAULT_TIME_ZONE = pytz.utc


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


def datetime_to_local_str(dattim):
    """Convert datetime to specified time_zone and returns a string."""
    return datetime_to_str(as_local(dattim))


def datetime_to_str(dattim):
    """Convert datetime to a string format.

    @rtype : str
    """
    return dattim.strftime(DATETIME_STR_FORMAT)


def datetime_to_time_str(dattim):
    """Convert datetime to a string containing only the time.

    @rtype : str
    """
    return dattim.strftime(TIME_STR_FORMAT)


def datetime_to_date_str(dattim):
    """Convert datetime to a string containing only the date.

    @rtype : str
    """
    return dattim.strftime(DATE_STR_FORMAT)


def str_to_datetime(dt_str, dt_format=DATETIME_STR_FORMAT):
    """Convert a string to a UTC datetime object.

    @rtype: datetime
    """
    try:
        return dt.datetime.strptime(
            dt_str, dt_format).replace(tzinfo=pytz.utc)
    except ValueError:  # If dt_str did not match our format
        return None


def date_str_to_date(dt_str):
    """Convert a date string to a date object."""
    try:
        return dt.datetime.strptime(dt_str, DATE_STR_FORMAT).date()
    except ValueError:  # If dt_str did not match our format
        return None


def strip_microseconds(dattim):
    """Return a copy of dattime object but with microsecond set to 0."""
    return dattim.replace(microsecond=0)


def parse_time_str(time_str):
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
