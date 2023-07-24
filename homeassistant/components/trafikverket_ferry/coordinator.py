"""DataUpdateCoordinator for the Trafikverket Ferry integration."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging
from typing import Any

from pytrafikverket import TrafikverketFerry
from pytrafikverket.exceptions import InvalidAuthentication, NoFerryFound
from pytrafikverket.trafikverket_ferry import FerryStop

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_WEEKDAY, WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
        self._time: time | None = dt_util.parse_time(entry.data[CONF_TIME])
        self._weekdays: list[str] = entry.data[CONF_WEEKDAY]

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Trafikverket."""

        departure_day = next_departuredate(self._weekdays)
        current_time = dt_util.now()
        when = (
            datetime.combine(
                departure_day,
                self._time,
                dt_util.get_time_zone(self.hass.config.time_zone),
            )
            if self._time
            else dt_util.now()
        )
        if current_time > when:
            when = current_time

        try:
            routedata: list[
                FerryStop
            ] = await self._ferry_api.async_get_next_ferry_stops(
                self._from, self._to, when, 3
            )
        except NoFerryFound as error:
            raise UpdateFailed(
                f"Departure {when} encountered a problem: {error}"
            ) from error
        except InvalidAuthentication as error:
            raise ConfigEntryAuthFailed(error) from error

        states = {
            "departure_time": routedata[0].departure_time,
            "departure_from": routedata[0].from_harbor_name,
            "departure_to": routedata[0].to_harbor_name,
            "departure_modified": routedata[0].modified_time,
            "departure_information": routedata[0].other_information,
            "departure_time_next": routedata[1].departure_time,
            "departure_time_next_next": routedata[2].departure_time,
        }
        _LOGGER.debug("States: %s", states)
        return states
