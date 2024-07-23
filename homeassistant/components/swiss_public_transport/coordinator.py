"""DataUpdateCoordinator for the swiss_public_transport integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TypedDict

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import OpendataTransportError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DOMAIN, SENSOR_CONNECTIONS_COUNT

_LOGGER = logging.getLogger(__name__)


class DataConnection(TypedDict):
    """A connection data class."""

    departure: datetime | None
    next_departure: datetime | None
    next_on_departure: datetime | None
    duration: int | None
    platform: str
    remaining_time: str
    start: str
    destination: str
    train_number: str
    transfers: int
    delay: int


def calculate_duration_in_seconds(duration_text: str) -> int | None:
    """Transform and calculate the duration into seconds."""
    # Transform 01d03:21:23 into 01 days 03:21:23
    duration_text_pg_format = duration_text.replace("d", " days ")
    duration = dt_util.parse_duration(duration_text_pg_format)
    return duration.seconds if duration else None


class SwissPublicTransportDataUpdateCoordinator(
    DataUpdateCoordinator[list[DataConnection]]
):
    """A SwissPublicTransport Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, opendata: OpendataTransport) -> None:
        """Initialize the SwissPublicTransport data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=90),
        )
        self._opendata = opendata

    def remaining_time(self, departure) -> timedelta | None:
        """Calculate the remaining time for the departure."""
        departure_datetime = dt_util.parse_datetime(departure)

        if departure_datetime:
            return departure_datetime - dt_util.as_local(dt_util.utcnow())
        return None

    def nth_departure_time(self, i: int) -> datetime | None:
        """Get nth departure time."""
        connections = self._opendata.connections
        if len(connections) > i and connections[i] is not None:
            return dt_util.parse_datetime(connections[i]["departure"])
        return None

    async def _async_update_data(self) -> list[DataConnection]:
        try:
            await self._opendata.async_get_data()
        except OpendataTransportError as e:
            _LOGGER.warning(
                "Unable to connect and retrieve data from transport.opendata.ch"
            )
            raise UpdateFailed from e

        connections = self._opendata.connections
        return [
            DataConnection(
                departure=self.nth_departure_time(i),
                next_departure=self.nth_departure_time(i + 1),
                next_on_departure=self.nth_departure_time(i + 2),
                train_number=connections[i]["number"],
                platform=connections[i]["platform"],
                transfers=connections[i]["transfers"],
                duration=calculate_duration_in_seconds(connections[i]["duration"]),
                start=self._opendata.from_name,
                destination=self._opendata.to_name,
                remaining_time=str(self.remaining_time(connections[i]["departure"])),
                delay=connections[i]["delay"],
            )
            for i in range(SENSOR_CONNECTIONS_COUNT)
            if len(connections) > i and connections[i] is not None
        ]
