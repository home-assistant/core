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
    return dt.datetime.now(CET).replace(minute=0, second=0, microsecond=0)


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


def _is_published(market_date: dt.date, time: dt.datetime) -> bool:
    """Returns whether OMIE data for a given date is expected to have been published at any point in time."""
    publish_date = market_date - dt.timedelta(days=1)
    publish_hour = _OMIE_PUBLISH_TIME_CET
    publish_time = dt.datetime.combine(publish_date, publish_hour, tzinfo=CET)

    return time >= publish_time


def get_market_dates(local_time: dt.datetime) -> set[dt.date]:
    """Returns the intraday market date(s) for a given local time.

    This will either return 1 or 2 dates, depending on whether the reference
    timezone aligns with CET day boundaries or not. This function only returns
    dates whose data is expected to be published by `time` (i.e. those for which
    the day-ahead market run for that date has already concluded before `time`).

    :param local_time the datetime at which the calculation is made
    """
    date_00_00 = dt.datetime.combine(local_time, dt.time.min, tzinfo=local_time.tzinfo)
    date_23_59 = dt.datetime.combine(local_time, dt.time.max, tzinfo=local_time.tzinfo)

    return {
        cet_date
        for day_boundary in (date_00_00, date_23_59)
        if (cet_date := day_boundary.astimezone(CET).date())
        if _is_published(cet_date, local_time)
    }
