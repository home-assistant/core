"""Helpers functions for the Workday component."""

from datetime import date, timedelta

from homeassistant.util import dt as dt_util

from .const import LOGGER


def validate_dates(holiday_list: list[str]) -> list[str]:
    """Validate and add to list of dates to add or remove."""
    calc_holidays: list[str] = []
    for add_date in holiday_list:
        if add_date.find(",") > 0:
            dates = add_date.split(",", maxsplit=1)
            d1 = dt_util.parse_date(dates[0])
            d2 = dt_util.parse_date(dates[1])
            if d1 is None or d2 is None:
                LOGGER.error("Incorrect dates in date range: %s", add_date)
                continue
            _range: timedelta = d2 - d1
            for i in range(_range.days + 1):
                day: date = d1 + timedelta(days=i)
                calc_holidays.append(day.strftime("%Y-%m-%d"))
            continue
        calc_holidays.append(add_date)
    return calc_holidays
