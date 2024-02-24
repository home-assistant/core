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
    duration: str
    platform: str
    remaining_time: str
    start: str
    destination: str
    train_number: str
    transfers: str
    delay: int


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

        return (
            departure_datetime - dt_util.as_local(dt_util.utcnow())
            if departure_datetime
            else None
        )

    async def _async_update_data(self) -> list[DataConnection]:
        try:
            await self._opendata.async_get_data()
        except OpendataTransportError as e:
            _LOGGER.warning(
                "Unable to connect and retrieve data from transport.opendata.ch"
            )
            raise UpdateFailed from e

        return [
            DataConnection(
                departure=dt_util.parse_datetime(
                    self._opendata.connections[i]["departure"]
                ),
                next_departure=dt_util.parse_datetime(
                    self._opendata.connections[i + 1]["departure"]
                )
                if len(self._opendata.connections) > i + 1
                and self._opendata.connections[i + 1] is not None
                else None,
                next_on_departure=dt_util.parse_datetime(
                    self._opendata.connections[i + 2]["departure"]
                )
                if len(self._opendata.connections) > i + 2
                and self._opendata.connections[i + 2] is not None
                else None,
                train_number=self._opendata.connections[i]["number"],
                platform=self._opendata.connections[i]["platform"],
                transfers=self._opendata.connections[i]["transfers"],
                duration=self._opendata.connections[i]["duration"],
                start=self._opendata.from_name,
                destination=self._opendata.to_name,
                remaining_time=str(
                    self.remaining_time(self._opendata.connections[i]["departure"])
                ),
                delay=self._opendata.connections[i]["delay"],
            )
            for i in range(SENSOR_CONNECTIONS_COUNT)
            if len(self._opendata.connections) > i
            and self._opendata.connections[i] is not None
        ]
