"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

import ns_api
import requests

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import Throttle, dt as dt_util

from .const import (
    CONF_STATION_FROM,
    CONF_STATION_TO,
    CONF_STATION_VIA,
    CONF_TIME,
    MIN_TIME_BETWEEN_UPDATES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""

    for subentry_id, subentry in entry.subentries.items():
        async_add_entities(
            [NSDepartureSensor(hass, subentry, entry.runtime_data.nsapi, subentry_id)],
            update_before_add=True,
            config_subentry_id=subentry_id,
        )


def valid_stations(stations, given_stations):
    """Verify the existence of the given station codes."""
    for station in given_stations:
        if station is None:
            continue
        if not any(s.code == station.upper() for s in stations):
            _LOGGER.warning("Station '%s' is not a valid station", station)
            return False
    return True


class NSDepartureSensor(SensorEntity):
    """Implementation of a NS Departure Sensor."""

    _attr_attribution = "Data provided by NS"
    _attr_icon = "mdi:train"
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigSubentry,
        nsapi: ns_api.NSAPI,
        unique_id: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._nsapi = nsapi
        self._name = entry.title
        self._departure = entry.data[CONF_STATION_FROM]
        self._via = entry.data[CONF_STATION_VIA]
        self._heading = entry.data[CONF_STATION_TO]
        self._time = entry.data[CONF_TIME]
        self._state = None
        self._trips = None
        self._first_trip = None
        self._next_trip = None
        self._attr_unique_id = unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> str | None:
        """Return the next departure time."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if not self._trips or self._first_trip is None:
            return None

        if self._first_trip.trip_parts:
            route = [self._first_trip.departure]
            route.extend(k.destination for k in self._first_trip.trip_parts)

        # Static attributes
        attributes = {
            "going": self._first_trip.going,
            "departure_time_planned": None,
            "departure_time_actual": None,
            "departure_delay": False,
            "departure_platform_planned": self._first_trip.departure_platform_planned,
            "departure_platform_actual": self._first_trip.departure_platform_actual,
            "arrival_time_planned": None,
            "arrival_time_actual": None,
            "arrival_delay": False,
            "arrival_platform_planned": self._first_trip.arrival_platform_planned,
            "arrival_platform_actual": self._first_trip.arrival_platform_actual,
            "next": None,
            "status": self._first_trip.status.lower(),
            "transfers": self._first_trip.nr_transfers,
            "route": route,
            "remarks": None,
        }

        # Planned departure attributes
        if self._first_trip.departure_time_planned is not None:
            attributes["departure_time_planned"] = (
                self._first_trip.departure_time_planned.strftime("%H:%M")
            )

        # Actual departure attributes
        if self._first_trip.departure_time_actual is not None:
            attributes["departure_time_actual"] = (
                self._first_trip.departure_time_actual.strftime("%H:%M")
            )

        # Delay departure attributes
        if (
            attributes["departure_time_planned"]
            and attributes["departure_time_actual"]
            and attributes["departure_time_planned"]
            != attributes["departure_time_actual"]
        ):
            attributes["departure_delay"] = True

        # Planned arrival attributes
        if self._first_trip.arrival_time_planned is not None:
            attributes["arrival_time_planned"] = (
                self._first_trip.arrival_time_planned.strftime("%H:%M")
            )

        # Actual arrival attributes
        if self._first_trip.arrival_time_actual is not None:
            attributes["arrival_time_actual"] = (
                self._first_trip.arrival_time_actual.strftime("%H:%M")
            )

        # Delay arrival attributes
        if (
            attributes["arrival_time_planned"]
            and attributes["arrival_time_actual"]
            and attributes["arrival_time_planned"] != attributes["arrival_time_actual"]
        ):
            attributes["arrival_delay"] = True

        # Next attributes
        if self._next_trip.departure_time_actual is not None:
            attributes["next"] = self._next_trip.departure_time_actual.strftime("%H:%M")
        elif self._next_trip.departure_time_planned is not None:
            attributes["next"] = self._next_trip.departure_time_planned.strftime(
                "%H:%M"
            )
        else:
            attributes["next"] = None

        return attributes

    @Throttle(timedelta(seconds=MIN_TIME_BETWEEN_UPDATES))
    async def async_update(self) -> None:
        """Get the trip information."""

        # Set the search parameter to search from a specific trip time
        # or to just search for next trip.
        if self._time:
            time = datetime.strptime(self._time, "%H:%M:%S")
            time = dt_util.find_next_time_expression_time(
                dt_util.now(), [time.second], [time.minute], [time.hour]
            )
            trip_time = time.strftime("%d-%m-%Y %H:%M")
        else:
            trip_time = dt_util.now().strftime("%d-%m-%Y %H:%M")

        try:
            loop = asyncio.get_running_loop()
            self._trips = await loop.run_in_executor(  # type: ignore[func-returns-value] # ns_api import contains to typing and causes a mypy error here.
                None,
                self._nsapi.get_trips,
                trip_time,
                self._departure,
                self._via,
                self._heading,
                True,
                0,
                2,
            )

            if self._trips:
                all_times = []

                # If a train is delayed we can observe this through departure_time_actual.
                for trip in self._trips:
                    if trip.departure_time_actual is None:
                        all_times.append(trip.departure_time_planned)
                    else:
                        all_times.append(trip.departure_time_actual)

                # Remove all trains that already left.
                filtered_times = [
                    (i, time)
                    for i, time in enumerate(all_times)
                    if time > dt_util.now()
                ]

                if len(filtered_times) > 0:
                    sorted_times = sorted(filtered_times, key=lambda x: x[1])
                    self._first_trip = self._trips[sorted_times[0][0]]
                    self._state = sorted_times[0][1].strftime("%H:%M")

                    # Filter again to remove trains that leave at the exact same time.
                    filtered_times = [
                        (i, time)
                        for i, time in enumerate(all_times)
                        if time > sorted_times[0][1]
                    ]

                    if len(filtered_times) > 0:
                        sorted_times = sorted(filtered_times, key=lambda x: x[1])
                        self._next_trip = self._trips[sorted_times[0][0]]
                    else:
                        self._next_trip = None

                else:
                    self._first_trip = None
                    self._state = None

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as error:
            _LOGGER.error("Couldn't fetch trip info: %s", error)
