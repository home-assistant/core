"""Utility functions for OMIE - Spain and Portugal electricity prices integration."""

import datetime as dt
from typing import Final
from zoneinfo import ZoneInfo

from pyomie.model import OMIEResults, _DataT
from pyomie.util import localize_hourly_data

from homeassistant.util.dt import utcnow

CET: Final = ZoneInfo("CET")

_OMIE_PUBLISH_TIME_CET = dt.time(hour=13, minute=30)
"""The time by which day-ahead market results (for the next day) will have been published to omie.es."""


def current_hour_CET() -> dt.datetime:
    """Returns the current hour in CET with minutes, seconds and microseconds equal to 0."""
    # to work out the start of the current hour we truncate from minutes downwards
    # rather than create a new datetime to ensure correctness across DST boundaries
    hour_start = utcnow().replace(minute=0, second=0, microsecond=0)
    return hour_start.astimezone(CET)


def pick_series_cet(
    res: OMIEResults[_DataT] | None,
    series_name: str,
) -> dict[dt.datetime, float]:
    """Pick the values for this series from the market data, keyed by a datetime in CET."""
    if res is None:
        return {}

    market_date = res.market_date
    series_data = getattr(res.contents, series_name, [])

    return {
        dt.datetime.fromisoformat(dt_str).astimezone(CET): v
        for dt_str, v in localize_hourly_data(market_date, series_data).items()
    }


def is_published(market_date: dt.date, now: dt.datetime) -> bool:
    """Returns whether OMIE data for a given date is expected to have been published at any point in time."""
    publish_date = market_date - dt.timedelta(days=1)
    publish_hour = _OMIE_PUBLISH_TIME_CET
    publish_time = dt.datetime.combine(publish_date, publish_hour, tzinfo=CET)

    return now >= publish_time


def get_market_dates(local_tz: ZoneInfo, date: dt.date) -> set[dt.date]:
    """Returns the intraday market date(s) for a date in a reference time zone.

    This will either return 1 or 2 dates, depending on whether the reference
    timezone aligns with CET day boundaries or not.

    :param local_tz the reference timezone to use when working out what "today" is
    :param date the date to consider
    """
    date_00_00 = dt.datetime.combine(date, dt.time.min, tzinfo=local_tz)
    date_23_59 = dt.datetime.combine(date, dt.time.max, tzinfo=local_tz)

    return {time.astimezone(CET).date() for time in (date_00_00, date_23_59)}
