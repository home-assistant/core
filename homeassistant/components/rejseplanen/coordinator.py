"""Data update coordinator for Rejseplanen."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from py_rejseplan.api.departures import DepartureBoard, departuresAPIClient
from py_rejseplan.dataclasses.departure import Departure
from py_rejseplan.exceptions import api_error, connection_error, http_error
from py_rejseplan.version import __version__ as py_rejseplan_version

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SCAN_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)


class RejseplanenDataUpdateCoordinator(DataUpdateCoordinator[DepartureBoard | None]):
    """Class to manage fetching data from the Rejseplanen API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        _LOGGER.info(
            "Initializing Rejseplanen Data Update Coordinator for Home Assistant with pyRejseplan version %s",
            py_rejseplan_version.version,
        )
        self.api = departuresAPIClient(auth_key=config_entry.data["authentication"])
        self._stop_ids: set[int] = set()

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} Data Update Coordinator",
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> DepartureBoard | None:
        """Update data via library."""
        try:
            return await self.hass.async_add_executor_job(self._fetch_data)
        except (
            api_error.RPAPIError,
            http_error.RPHTTPError,
        ) as error:  # runtime errors from the API
            raise UpdateFailed(error) from error
        except connection_error.RPConnectionError as error:  # network errors
            _LOGGER.error("Connection error while fetching data: %s", error)
            raise UpdateFailed(error) from error
        except TypeError as error:
            _LOGGER.error(
                "Type error fetching data for stop %s: %s", self._stop_ids, error
            )
            raise UpdateFailed(error) from error
        except Exception as error:
            _LOGGER.error("Error fetching data for stop %s: %s", self._stop_ids, error)
            raise UpdateFailed(error) from error

    def due_in_minutes(self, timestamp) -> int:
        """Get the time in minutes from a timestamp.

        The timestamp should be in the format day.month.year hour:minute
        """
        diff = datetime.strptime(
            timestamp, "%Y-%m-%d %H:%M:%S"
        ) - dt_util.now().replace(tzinfo=None)

        return int(diff.total_seconds() // 60)

    def add_stop_id(self, stop_id: int):
        """Add a stop ID to the coordinator."""
        self._stop_ids.add(stop_id)

    def remove_stop_id(self, stop_id: int):
        """Remove a stop ID from the coordinator."""
        self._stop_ids.discard(stop_id)

    def _fetch_data(self) -> DepartureBoard | None:
        """Fetch data from Rejseplanen API."""
        if not self._stop_ids:
            _LOGGER.debug("No stop IDs registered, skipping data fetch")
            _LOGGER.warning(
                "No stops registered, Please add a stop through the UI configuration. Data not fetched"
            )
            return None
        _LOGGER.debug("Fetching data for stop IDs: %s", self._stop_ids)
        # Get all departures for this stop
        departure_board, _ = self.api.get_departures(list(self._stop_ids))
        return departure_board

    def get_filtered_departures(
        self,
        stop_id,
        route_filter=None,
        direction_filter=None,
        departure_type_filter=None,
    ) -> list[Departure]:
        """Get departures filtered by the specified criteria."""
        if not self.data:
            return []

        if hasattr(self.data, "departures"):
            departures = self.data.departures
        else:
            return []

        filtered_data = [
            departure for departure in departures if departure.stopExtId == stop_id
        ]

        if direction_filter:
            filtered_data = [
                d for d in filtered_data if d.direction in direction_filter
            ]

        if departure_type_filter:
            filtered_data = [
                d for d in filtered_data if (d.product.cls & departure_type_filter)
            ]

        # Sort by due_in time
        filtered_data.sort(
            key=lambda x: (
                x.rtDate if x.rtDate else x.date,
                x.rtTime if x.rtTime else x.time,
            ),
        )
        now = dt_util.now().replace(tzinfo=None)

        # Find the index where the departure time is not in the past
        def departure_datetime(d: Departure) -> datetime:
            return datetime.strptime(
                f"{d.rtDate if d.rtDate else d.date} {d.rtTime if d.rtTime else d.time}",
                "%Y-%m-%d %H:%M:%S",
            )

        idx = next(
            (
                i
                for i, d in enumerate(filtered_data)
                if (departure_datetime(d) - now >= timedelta(minutes=0))
            ),
            len(filtered_data),
        )
        return filtered_data[idx:]


class NoStopsRegisteredError(HomeAssistantError):
    """Error to indicate that no stop IDs are registered in the coordinator."""

    def __init__(
        self, message: str = "No stop IDs registered in the coordinator."
    ) -> None:
        """Initialize the error with a message."""
        super().__init__(message)
        self.message = message
