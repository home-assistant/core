"""DataUpdateCoordinator for the Trafikverket Ferry integration."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging
from typing import Any

from pytrafikverket import TrafikverketFerry
from pytrafikverket.trafikverket_ferry import FerryStop

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_WEEKDAY, WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import UTC, as_utc, parse_time

from .const import CONF_FROM, CONF_TIME, CONF_TO, DOMAIN

_LOGGER = logging.getLogger(__name__)
TIME_BETWEEN_UPDATES = timedelta(minutes=5)


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


class TVDataUpdateCoordinator(DataUpdateCoordinator):
    """A Trafikverket Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Trafikverket coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=TIME_BETWEEN_UPDATES,
        )
        self._ferry_api = TrafikverketFerry(
            async_get_clientsession(hass), entry.data[CONF_API_KEY]
        )
        self._from: str = entry.data[CONF_FROM]
        self._to: str = entry.data[CONF_TO]
        self._time: time | None = parse_time(entry.data[CONF_TIME])
        self._weekdays: list[str] = entry.data[CONF_WEEKDAY]

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Trafikverket."""

        departure_day = next_departuredate(self._weekdays)
        currenttime = datetime.now()
        when = (
            datetime.combine(departure_day, self._time)
            if self._time
            else datetime.now()
        )
        if currenttime > when:
            when = currenttime

        try:
            routedata: FerryStop = await self._ferry_api.async_get_next_ferry_stop(
                self._from, self._to, when
            )
        except ValueError as error:
            raise UpdateFailed(
                f"Departure {when} encountered a problem: {error}"
            ) from error

        states = {
            "departure_time": routedata.departure_time.replace(tzinfo=UTC),
            "departure_from": routedata.from_harbor_name,
            "departure_to": routedata.to_harbor_name,
            "departure_modified": as_utc(routedata.modified_time.replace(tzinfo=UTC)),
            "departure_information": routedata.other_information,
        }
        return states
