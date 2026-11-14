"""DataUpdateCoordinator for the swiss_public_transport integration."""

from datetime import datetime, timedelta
import logging
from typing import TypedDict, override

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import (
    CONF_TIME_FIXED,
    CONF_TIME_STATION,
    CONNECTIONS_COUNT,
    DEFAULT_TIME_STATION,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
)
from .helper import offset_opendata

_LOGGER = logging.getLogger(__name__)

# Spare connections which replace departed ones until the next update
CONNECTIONS_SPARE = 2
DEPARTED_GRACE = timedelta(seconds=30)

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


def _departed_at(connection: DataConnection) -> datetime | None:
    """Return when a connection counts as departed."""
    if (departure := connection["departure"]) is None:
        return None
    return departure + timedelta(minutes=connection["delay"] or 0) + DEPARTED_GRACE


class SwissPublicTransportDataUpdateCoordinator(
    DataUpdateCoordinator[list[DataConnection]]
):
    """A SwissPublicTransport Data Update Coordinator."""

    config_entry: SwissPublicTransportConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SwissPublicTransportConfigEntry,
        opendata: OpendataTransport,
        time_offset: dict[str, int] | None,
    ) -> None:
        """Initialize the SwissPublicTransport data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_TIME),
        )
        self._opendata = opendata
        self._time_offset = time_offset
        # A fixed time or an arrival time returns connections which already left
        self._drop_departed = (
            CONF_TIME_FIXED not in config_entry.data
            and config_entry.data.get(CONF_TIME_STATION, DEFAULT_TIME_STATION)
            == "departure"
        )
        self._unsub_departed: CALLBACK_TYPE | None = None

    def remaining_time(self, departure) -> timedelta | None:
        """Calculate the remaining time for the departure."""
        departure_datetime = dt_util.parse_datetime(departure)

        if departure_datetime:
            return departure_datetime - dt_util.as_local(dt_util.utcnow())
        return None

    @override
    async def _async_update_data(self) -> list[DataConnection]:
        if not self._drop_departed:
            return await self.fetch_connections(limit=CONNECTIONS_COUNT)
        connections = self._async_remaining(
            await self.fetch_connections(limit=CONNECTIONS_COUNT + CONNECTIONS_SPARE)
        )
        self._async_schedule_departed(connections)
        return connections

    @override
    async def async_shutdown(self) -> None:
        self._async_cancel_departed()
        await super().async_shutdown()

    @callback
    def _async_remaining(
        self, connections: list[DataConnection]
    ) -> list[DataConnection]:
        """Return the connections which have not departed yet."""
        now = dt_util.utcnow()
        return [
            connection
            for connection in connections
            if (departed := _departed_at(connection)) is None or departed > now
        ]

    @callback
    def _async_cancel_departed(self) -> None:
        """Cancel the removal of the next departing connection."""
        if self._unsub_departed:
            self._unsub_departed()
            self._unsub_departed = None

    @callback
    def _async_schedule_departed(self, connections: list[DataConnection]) -> None:
        """Schedule the removal of the next departing connection."""
        self._async_cancel_departed()
        if not connections or (departed := _departed_at(connections[0])) is None:
            return
        self._unsub_departed = async_track_point_in_time(
            self.hass, self._async_handle_departed, departed
        )

    @callback
    def _async_handle_departed(self, now: datetime) -> None:
        """Remove the departed connection, the next ones move up."""
        self._unsub_departed = None
        self.data = self._async_remaining(self.data)
        self.async_update_listeners()
        self._async_schedule_departed(self.data)

    async def fetch_connections(self, limit: int) -> list[DataConnection]:
        """Fetch connections using the opendata api."""
        self._opendata.limit = limit
        if self._time_offset:
            offset_opendata(self._opendata, self._time_offset)

        try:
            await self._opendata.async_get_data()
        except OpendataTransportConnectionError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_connection_failed",
            ) from e
        except OpendataTransportError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from e
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
