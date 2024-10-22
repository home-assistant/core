"""DataUpdateCoordinator for the swiss_public_transport integration."""

from __future__ import annotations

from datetime import datetime, time, timedelta
import logging
from typing import TypedDict

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import (
    CONNECTIONS_COUNT,
    DEFAULT_DEPARTURE_MODE,
    DEFAULT_DEPARTURE_TIME,
    DEFAULT_DEPARTURE_TIME_OFFSET_MINUTES,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY_FORMAT = "{domain}.{entry_id}"
STORAGE_VERSION = 1

type SwissPublicTransportConfigEntry = ConfigEntry[
    SwissPublicTransportDataUpdateCoordinator
]


class ConfigConnection(TypedDict):
    """A connection config class."""

    departure_mode: str
    departure_time_offset: float
    departure_time: str


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

    def __init__(self, hass: HomeAssistant, opendata: OpendataTransport) -> None:
        """Initialize the SwissPublicTransport data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_TIME),
        )
        self._opendata = opendata
        self._store = Store[ConfigConnection](
            hass,
            STORAGE_VERSION,
            STORAGE_KEY_FORMAT.format(
                domain=DOMAIN, entry_id=self.config_entry.entry_id
            ),
        )
        self._config: ConfigConnection | None = None

    async def _async_setup(self):
        """Set up the coordinator."""
        await self.load_store()

    async def load_store(self):
        """Load the store."""
        self._config = await self._store.async_load() or ConfigConnection(
            departure_mode=DEFAULT_DEPARTURE_MODE,
            departure_time=DEFAULT_DEPARTURE_TIME,
            departure_time_offset=timedelta(
                minutes=DEFAULT_DEPARTURE_TIME_OFFSET_MINUTES
            ).total_seconds(),
        )

    async def save_store(self):
        """Save the store."""
        await self._store.async_save(self._config)

    @property
    def departure_mode(self) -> str:
        """Return the departure mode of the config."""
        if self._config:
            return self._config["departure_mode"]
        return DEFAULT_DEPARTURE_MODE

    @departure_mode.setter
    def departure_mode(self, value: str) -> None:
        """Set the departure mode of the config."""
        if self._config:
            self._config["departure_mode"] = value

    @property
    def departure_time(self) -> time:
        """Return the departure time of the config."""
        if self._config:
            return time.fromisoformat(self._config["departure_time"])
        return time.fromisoformat(DEFAULT_DEPARTURE_TIME)

    @departure_time.setter
    def departure_time(self, value: time) -> None:
        """Set the departure time of the config."""
        if self._config:
            self._config["departure_time"] = value.isoformat()

    @property
    def departure_time_offset(self) -> timedelta:
        """Return the departure time offset of the config."""
        if self._config:
            return timedelta(seconds=self._config["departure_time_offset"])
        return timedelta(minutes=DEFAULT_DEPARTURE_TIME_OFFSET_MINUTES)

    @departure_time_offset.setter
    def departure_time_offset(self, value: timedelta) -> None:
        """Set the departure time offset of the config."""
        if self._config:
            self._config["departure_time_offset"] = value.total_seconds()

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
        assert self._config
        self._opendata.limit = limit
        now = dt_util.now()
        if self._config["departure_mode"] == "now":
            now_local = dt_util.as_local(now)
            self._opendata.date = now_local.date()
            self._opendata.time = now_local.time()
        elif self._config["departure_mode"] == "relative":
            now_local_offset = dt_util.as_local(
                dt_util.now() + self.departure_time_offset
            )
            self._opendata.date = now_local_offset.date()
            self._opendata.time = now_local_offset.time()
        elif self._config["departure_mode"] == "absolute":
            now_local = dt_util.as_local(now)
            time_of_day = self.departure_time
            self._opendata.date = (
                now_local.date()
                if time_of_day > now_local.time()
                else (now_local + timedelta(days=1)).date()
            )
            self._opendata.time = time_of_day

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
                line=connections[i]["line"],
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
                "line": connection["line"],
            }
            for connection in await self.fetch_connections(limit)
        ]
