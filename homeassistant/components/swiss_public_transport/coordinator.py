"""DataUpdateCoordinator for the swiss_public_transport integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TypedDict

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import CONNECTIONS_COUNT, DEFAULT_UPDATE_TIME, DOMAIN
from .helper import offset_opendata

_LOGGER = logging.getLogger(__name__)

type SwissPublicTransportConfigEntry = ConfigEntry[
    SwissPublicTransportDataUpdateCoordinator
]


class DataConnection(TypedDict):
    """A connection data class."""

    departure: datetime | None
    duration: int | None
    platform: str
    remaining_time: str
    start: str
    destination: str
    train_number: str
    transfers: int
    delay: int
    line: str


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

    config_entry: SwissPublicTransportConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        opendata: OpendataTransport,
        time_offset: dict[str, int] | None,
    ) -> None:
        """Initialize the SwissPublicTransport data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_TIME),
        )
        self._opendata = opendata
        self._time_offset = time_offset

    def remaining_time(self, departure) -> timedelta | None:
        """Calculate the remaining time for the departure."""
        departure_datetime = dt_util.parse_datetime(departure)

        if departure_datetime:
            return departure_datetime - dt_util.as_local(dt_util.utcnow())
        return None

    async def _async_update_data(self) -> list[DataConnection]:
        return await self.fetch_connections(limit=CONNECTIONS_COUNT)

    async def fetch_connections(self, limit: int) -> list[DataConnection]:
        """Fetch connections using the opendata api."""
        self._opendata.limit = limit
        if self._time_offset:
            offset_opendata(self._opendata, self._time_offset)

        try:
            await self._opendata.async_get_data()
        except OpendataTransportConnectionError as e:
            _LOGGER.warning("Connection to transport.opendata.ch cannot be established")
            raise UpdateFailed from e
        except OpendataTransportError as e:
            _LOGGER.warning(
                "Unable to connect and retrieve data from transport.opendata.ch"
            )
            raise UpdateFailed from e
        connections = self._opendata.connections
        return [
            DataConnection(
                departure=dt_util.parse_datetime(connections[i]["departure"]),
                train_number=connections[i]["number"],
                platform=connections[i]["platform"],
                transfers=connections[i]["transfers"],
                duration=calculate_duration_in_seconds(connections[i]["duration"]),
                start=self._opendata.from_name,
                destination=self._opendata.to_name,
                remaining_time=str(self.remaining_time(connections[i]["departure"])),
                delay=connections[i]["delay"],
                line=connections[i].get("line"),
            )
            for i in range(limit)
            if len(connections) > i and connections[i] is not None
        ]

    async def fetch_connections_as_json(self, limit: int) -> list[JsonValueType]:
        """Fetch connections using the opendata api."""
        return [
            {
                "departure": connection["departure"].isoformat()
                if connection["departure"]
                else None,
                "duration": connection["duration"],
                "platform": connection["platform"],
                "remaining_time": connection["remaining_time"],
                "start": connection["start"],
                "destination": connection["destination"],
                "train_number": connection["train_number"],
                "transfers": connection["transfers"],
                "delay": connection["delay"],
                "line": connection.get("line"),
            }
            for connection in await self.fetch_connections(limit)
        ]
