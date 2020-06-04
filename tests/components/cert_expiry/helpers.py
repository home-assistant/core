"""Helpers for Cert Expiry tests."""
from datetime import timedelta

from homeassistant.util import dt


def make_timestamp(days):
    """Create timestamp object for requested days in future."""
    delta = timedelta(days=days, minutes=1)
    return dt.now() + delta
