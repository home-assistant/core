"""
homeassistant.util.dt
~~~~~~~~~~~~~~~~~~~~~

Provides helper methods to handle the time in HA.

"""
import datetime as dt

import pytz

DATE_STR_FORMAT = "%H:%M:%S %d-%m-%Y"
UTC = DEFAULT_TIME_ZONE = pytz.utc


def set_default_time_zone(time_zone):
    """ Sets a default time zone to be used when none is specified. """
    global DEFAULT_TIME_ZONE  # pylint: disable=global-statement

    assert isinstance(time_zone, dt.tzinfo)

    DEFAULT_TIME_ZONE = time_zone


def get_time_zone(time_zone_str):
    """ Get time zone from string. Return None if unable to determine. """
    try:
        return pytz.timezone(time_zone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        return None


def utcnow():
    """ Get now in UTC time. """
    return dt.datetime.now(pytz.utc)


def now(time_zone=None):
    """ Get now in specified time zone. """
    return dt.datetime.now(time_zone or DEFAULT_TIME_ZONE)


def as_utc(dattim):
    """ Return a datetime as UTC time.
        Assumes datetime without tzinfo to be in the DEFAULT_TIME_ZONE. """
    if dattim.tzinfo == pytz.utc:
        return dattim
    elif dattim.tzinfo is None:
        dattim = dattim.replace(tzinfo=DEFAULT_TIME_ZONE)

    return dattim.astimezone(pytz.utc)


def as_local(dattim):
    """ Converts a UTC datetime object to local time_zone. """
    if dattim.tzinfo == DEFAULT_TIME_ZONE:
        return dattim
    elif dattim.tzinfo is None:
        dattim = dattim.replace(tzinfo=pytz.utc)

    return dattim.astimezone(DEFAULT_TIME_ZONE)


def utc_from_timestamp(timestamp):
    """ Returns a UTC time from a timestamp. """
    return dt.datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.utc)


def datetime_to_local_str(dattim, time_zone=None):
    """ Converts datetime to specified time_zone and returns a string. """
    return datetime_to_str(as_local(dattim))


def datetime_to_str(dattim):
    """ Converts datetime to a string format.

    @rtype : str
    """
    return dattim.strftime(DATE_STR_FORMAT)


def str_to_datetime(dt_str):
    """ Converts a string to a UTC datetime object.

    @rtype: datetime
    """
    try:
        return dt.datetime.strptime(
            dt_str, DATE_STR_FORMAT).replace(tzinfo=pytz.utc)
    except ValueError:  # If dt_str did not match our format
        return None


def strip_microseconds(dattim):
    """ Returns a copy of dattime object but with microsecond set to 0. """
    return dattim.replace(microsecond=0)
