"""Utils for trafikverket_train."""

from __future__ import annotations

from datetime import date, time, timedelta

from homeassistant.const import WEEKDAYS


def create_unique_id(
    from_station: str, to_station: str, depart_time: time | str | None, weekdays: list
) -> str:
    """Create unique id."""
    timestr = str(depart_time) if depart_time else ""
    return (
        f"{from_station.casefold().replace(' ', '')}-{to_station.casefold().replace(' ', '')}"
        f"-{timestr.casefold().replace(' ', '')}-{weekdays!s}"
    )


def next_weekday(fromdate: date, weekday: int) -> date:
    """Return the date of the next time a specific weekday happen."""
    days_ahead = weekday - fromdate.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return fromdate + timedelta(days_ahead)


def next_departuredate(departure: list[str]) -> date:
    """Calculate the next departuredate from an array input of short days."""
    today_date = date.today()
    today_weekday = date.weekday(today_date)
    if WEEKDAYS[today_weekday] in departure:
        return today_date
    for day in departure:
        next_departure = WEEKDAYS.index(day)
        if next_departure > today_weekday:
            return next_weekday(today_date, next_departure)
    return next_weekday(today_date, WEEKDAYS.index(departure[0]))
