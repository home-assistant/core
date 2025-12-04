"""Utility functions for OMIE - Spain and Portugal electricity prices integration."""

import datetime as dt
from typing import Final
from zoneinfo import ZoneInfo

from pyomie.model import OMIEResults, SpotData
from pyomie.util import localize_quarter_hourly_data

CET: Final = ZoneInfo("CET")


def current_quarter_hour_cet() -> dt.datetime:
    """Returns the current quarter-hour in CET with seconds and microseconds equal to 0."""
    now = dt.datetime.now(CET)
    floored_minute = now.minute // 15 * 15
    return now.replace(minute=floored_minute, second=0, microsecond=0)


def pick_series_cet(
    res: OMIEResults[SpotData] | None,
    series_name: str,
) -> dict[dt.datetime, float]:
    """Pick the values for this series from the market data, keyed by a datetime in CET."""
    if res is None:
        return {}

    market_date = res.market_date
    series_data = getattr(res.contents, series_name, [])

    return {
        dt.datetime.fromisoformat(dt_str).astimezone(CET): series_values
        for dt_str, series_values in localize_quarter_hourly_data(
            market_date, series_data
        ).items()
    }
