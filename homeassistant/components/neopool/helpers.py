"""Helper functions for the NeoPool integration."""

import datetime

import homeassistant.util.dt as dt_util


def calculate_next_interval_time(seconds: float | None) -> datetime.datetime | None:
    """Return the timestamp for the next interval start, rounded to the nearest minute.

    Returns None if seconds is None or <= 0. Always returns UTC; the HA
    frontend localises the display.
    """
    if not seconds or seconds <= 0:
        return None
    target = dt_util.utcnow() + datetime.timedelta(seconds=seconds)
    return target.replace(second=0, microsecond=0)
