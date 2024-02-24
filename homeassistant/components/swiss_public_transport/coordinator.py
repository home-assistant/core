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
    duration: str
    platform: str
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
                train_number=self._opendata.connections[i]["number"],
                platform=self._opendata.connections[i]["platform"],
                transfers=self._opendata.connections[i]["transfers"],
                duration=self._opendata.connections[i]["duration"],
                start=self._opendata.from_name,
                destination=self._opendata.to_name,
                delay=self._opendata.connections[i]["delay"],
            )
            for i in range(SENSOR_CONNECTIONS_COUNT)
            if len(self._opendata.connections) > i
            and self._opendata.connections[i] is not None
        ]
