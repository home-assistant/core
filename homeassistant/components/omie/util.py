"""Utility functions for OMIE - Spain and Portugal electricity prices integration."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from pyomie.model import OMIEResults, _DataT
from pyomie.util import localize_hourly_data

from .const import CET

_OMIE_PUBLISH_TIME_CET = dt.time(hour=13, minute=30)
"""The time by which day-ahead market results (for the next day) will have been published to omie.es."""


def _pick_series_cet(
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


def _is_published(market_date: dt.date, fetch_time: dt.datetime) -> bool:
    """Returns whether OMIE data for a given date is expected to have been published at any point in time."""
    publish_date = market_date - dt.timedelta(days=1)
    publish_hour = _OMIE_PUBLISH_TIME_CET
    publish_time = dt.datetime.combine(publish_date, publish_hour, tzinfo=CET)

    return fetch_time >= publish_time


def _get_market_dates(local_tz: ZoneInfo, now_time: dt.datetime) -> set[dt.date]:
    """Returns the intraday market date(s) whose data we need to fetch."""
    min_max = [_OMIE_PUBLISH_TIME_CET.min, _OMIE_PUBLISH_TIME_CET.max]
    return {
        dt.datetime.combine(now_time.astimezone(local_tz), t, tzinfo=local_tz)
        .astimezone(CET)
        .date()
        for t in min_max
    }
