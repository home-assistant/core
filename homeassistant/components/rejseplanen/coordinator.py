"""Data update coordinator for Rejseplanen."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from py_rejseplan.api.departures import DeparturesAPIClient
from py_rejseplan.dataclasses.departure import Departure
from py_rejseplan.dataclasses.departure_board import DepartureBoard
from py_rejseplan.exceptions import APIError, ConnectionError, HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_API_KEY, CONF_STOP_ID, DOMAIN, SCAN_INTERVAL_MINUTES
from .helpers import cph_to_tz

_LOGGER = logging.getLogger(__name__)

type RejseplanenConfigEntry = ConfigEntry[RejseplanenDataUpdateCoordinator]


class RejseplanenDataUpdateCoordinator(DataUpdateCoordinator[DepartureBoard]):
    """Class to manage fetching data from the Rejseplanen API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RejseplanenConfigEntry,
    ) -> None:
        """Initialize."""

        self.api = DeparturesAPIClient(auth_key=config_entry.data[CONF_API_KEY])
        self.last_update_success_time: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} Data Update Coordinator",
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> DepartureBoard:
        """Update data via library."""
        assert self.config_entry is not None
        try:
            stop_ids = {
                subentry.data[CONF_STOP_ID]
                for subentry in self.config_entry.subentries.values()
                if subentry.subentry_type == "stop"
            }
            board = await self.hass.async_add_executor_job(self._fetch_data, stop_ids)
        except (APIError, HTTPError) as error:  # runtime errors from the API
            raise UpdateFailed(error) from error
        except ConnectionError as error:  # network errors
            raise UpdateFailed(
                f"Connection error while fetching data: {error}"
            ) from error
        except TypeError as error:
            raise UpdateFailed(
                f"Type error fetching data for stop {stop_ids}: {error}"
            ) from error

        self.last_update_success_time = dt_util.now()
        return board

    def _fetch_data(self, stop_ids: set[int]) -> DepartureBoard:
        """Fetch data from Rejseplanen API."""
        if not stop_ids:
            _LOGGER.debug(
                "No stops registered, Please add a stop through the UI configuration. Data not fetched"
            )
            return DepartureBoard(
                serverVersion="",
                dialectVersion="",
                planRtTs=dt_util.utcnow(),
                requestId="",
                technicalMessages=[],
                departures=[],
            )
        # Get all departures for this stop
        _LOGGER.debug("Fetching data for stop IDs: %s", stop_ids)
        departure_board, _ = self.api.get_departures(list(stop_ids))
        return departure_board

    def get_filtered_departures(
        self: RejseplanenDataUpdateCoordinator,
        stop_id: int,
        direction_filter: list[str] | None = None,
        departure_type_filter: int | None = None,
    ) -> list[Departure]:
        """Get departures filtered by the specified criteria."""

        if not self.data:
            return []

        filtered_data = [
            departure
            for departure in self.data.departures
            if departure.stopExtId == stop_id
        ]

        if direction_filter:
            filtered_data = [
                d for d in filtered_data if d.direction in direction_filter
            ]

        if departure_type_filter:
            filtered_data = [
                d
                for d in filtered_data
                if d.product.cls_id is not None
                and (d.product.cls_id & departure_type_filter)
            ]

        # Sort by due_in time
        filtered_data.sort(
            key=lambda x: (
                x.rtDate or x.date,
                x.rtTime or x.time,
            ),
        )
        now = dt_util.utcnow()

        # Find the index where the departure time is not in the past
        def departure_datetime(d: Departure) -> datetime:
            date = d.rtDate or d.date
            time = d.rtTime or d.time
            naive_dt = datetime.combine(date, time)
            return cph_to_tz(naive_dt.date(), naive_dt.time(), dt_util.UTC)

        idx = next(
            (
                i
                for i, d in enumerate(filtered_data)
                if (departure_datetime(d) - now >= timedelta(minutes=0))
            ),
            len(filtered_data),
        )
        return filtered_data[idx:]
