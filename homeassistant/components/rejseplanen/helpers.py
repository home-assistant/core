"""Helpers for timezone conversion for the Rejseplanen integration."""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from homeassistant.util import dt as dt_util

COPENHAGEN_TZ = dt_util.get_time_zone("Europe/Copenhagen")


def cph_to_tz(dt_date: date, dt_time: time, target_tz: ZoneInfo | timezone) -> datetime:
    """Return a datetime in the target_tz, assuming input is Copenhagen local time."""
    cph_naive = datetime.combine(dt_date, dt_time)
    cph_aware = cph_naive.replace(tzinfo=COPENHAGEN_TZ)
    return cph_aware.astimezone(target_tz)
