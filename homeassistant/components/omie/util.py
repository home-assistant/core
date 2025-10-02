"""Utility functions for OMIE - Spain and Portugal electricity prices integration."""

import datetime as dt
from typing import Final
from zoneinfo import ZoneInfo

from pyomie.model import OMIEResults, _DataT
from pyomie.util import localize_quarter_hourly_data

CET: Final = ZoneInfo("CET")

_OMIE_PUBLISH_TIME_CET = dt.time(hour=13, minute=30)
"""The time by which day-ahead market results (for the next day) will have been published to omie.es."""


def current_quarter_hour_cet() -> dt.datetime:
    """Returns the current quarter-hour in CET with seconds and microseconds equal to 0."""
    # to work out the start of the current hour we truncate from minutes downwards
    # rather than create a new datetime to ensure correctness across DST boundaries
    now = dt.datetime.now(CET)
    return now.replace(minute=now.minute // 15 * 15, second=0, microsecond=0)


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
        for dt_str, v in localize_quarter_hourly_data(market_date, series_data).items()
    }


def get_market_dates(local_time: dt.datetime) -> set[dt.date]:
    """Returns the intraday market date(s) for a given local time.

    :param local_time the datetime at which the calculation is made
    """

    return {local_time.astimezone(CET).date()}
