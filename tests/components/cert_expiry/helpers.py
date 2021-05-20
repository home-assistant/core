"""Helpers for Cert Expiry tests."""
from datetime import datetime, timedelta

from homeassistant.util import dt


def static_datetime():
    """Build a datetime object for testing in the correct timezone."""
    return dt.as_utc(datetime(2020, 6, 12, 8, 0, 0))


def future_timestamp(days):
    """Create timestamp object for requested days in future."""
    delta = timedelta(days=days, minutes=1)
    return static_datetime() + delta
