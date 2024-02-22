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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DataConnection(TypedDict):
    """A connection data class."""

    departure: datetime | None
    next_departure: str | None
    next_on_departure: str | None
    duration: str
    platform: str
    remaining_time: str
    start: str
    destination: str
    train_number: str
    transfers: str
    delay: int


class SwissPublicTransportDataUpdateCoordinator(DataUpdateCoordinator[DataConnection]):
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

    async def _async_update_data(self) -> DataConnection:
        try:
            await self._opendata.async_get_data()
        except OpendataTransportError as e:
            _LOGGER.warning(
                "Unable to connect and retrieve data from transport.opendata.ch"
            )
            raise UpdateFailed from e

        departure_time = (
            dt_util.parse_datetime(self._opendata.connections[0]["departure"])
            if self._opendata.connections[0] is not None
            else None
        )
        next_departure_time = (
            dt_util.parse_datetime(self._opendata.connections[1]["departure"])
            if self._opendata.connections[1] is not None
            else None
        )
        next_on_departure_time = (
            dt_util.parse_datetime(self._opendata.connections[2]["departure"])
            if self._opendata.connections[2] is not None
            else None
        )

        if departure_time:
            remaining_time = departure_time - dt_util.as_local(dt_util.utcnow())
        else:
            remaining_time = None

        return DataConnection(
            departure=departure_time,
            next_departure=next_departure_time.isoformat()
            if next_departure_time is not None
            else None,
            next_on_departure=next_on_departure_time.isoformat()
            if next_on_departure_time is not None
            else None,
            train_number=self._opendata.connections[0]["number"],
            platform=self._opendata.connections[0]["platform"],
            transfers=self._opendata.connections[0]["transfers"],
            duration=self._opendata.connections[0]["duration"],
            start=self._opendata.from_name,
            destination=self._opendata.to_name,
            remaining_time=f"{remaining_time}",
            delay=self._opendata.connections[0]["delay"],
        )
