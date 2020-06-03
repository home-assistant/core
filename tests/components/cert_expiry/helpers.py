"""Helpers for Cert Expiry tests."""
from datetime import datetime, timedelta


def make_timestamp(days):
    """Create timestamp object for requested days in future."""
    delta = timedelta(days=days, minutes=1)
    return datetime.now() + delta
