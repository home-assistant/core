"""Helpers for Cert Expiry tests."""

from datetime import UTC, datetime, timedelta


def datetime_today():
    """Return the current day without time."""
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def past_timestamp(days):
    """Create timestamp object for requested days in the past."""
    delta = timedelta(days=days, minutes=1)
    return datetime_today() - delta


def future_timestamp(days):
    """Create timestamp object for requested days in future."""
    delta = timedelta(days=days, minutes=1)
    return datetime_today() + delta
