"""Utility functions for OMIE - Spain and Portugal electricity prices integration."""
import datetime as dt
from zoneinfo import ZoneInfo

from pyomie.model import OMIEResults, _DataT
from pyomie.util import localize_hourly_data

from .const import CET


def enumerate_hours_of_day(time_zone: ZoneInfo, date: dt.date) -> list[dt.datetime]:
    """Enumerate all hours in a given day of a time zone, taking into account DST changeover (some days will have 23 or 25 hours).

    @param time_zone: the time zone that the date relates to
    @param date: the date
    @return: all hours of the given date
    """
    hour0 = dt.datetime(date.year, date.month, date.day, tzinfo=time_zone).astimezone(
        dt.UTC
    )

    def hour_n_of_day(n: int) -> dt.datetime:
        return (hour0 + dt.timedelta(hours=n)).astimezone(time_zone)

    return [
        hour
        for hour in [hour_n_of_day(n) for n in range(25)]
        if hour.date() == date  # 25th hour occurs on DST changeover only
    ]


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
