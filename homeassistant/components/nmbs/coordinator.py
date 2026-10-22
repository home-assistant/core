"""Data update coordinator for the NMBS integration."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
import logging
from typing import override

from pyrail import IRail, PyRailError
from pyrail.models import (
    ConnectionDetails,
    ConnectionsApiResponse,
    LiveboardApiResponse,
    LiveboardDeparture,
    StationDetails,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_EXCLUDE_VIAS,
    CONF_STATION_FROM,
    CONF_STATION_TO,
    CONNECTION_FEED,
    CONNECTION_UNIQUE_ID_PREFIX,
    DOMAIN,
    LIVEBOARD_UNIQUE_ID_PREFIX,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)

type NMBSConfigEntry = ConfigEntry[NMBSCoordinator]


@dataclass
class NMBSData:
    """Data fetched by the NMBS coordinator."""

    connection: ConnectionDetails | None
    next_departures: dict[str, LiveboardDeparture | None]
    failed_feeds: set[str]


@dataclass
class FeedResult[T]:
    """Result of one pyrail feed request."""

    data: T | None
    error: Exception | None


def _find_station(
    stations: list[StationDetails], station_id: str
) -> StationDetails | None:
    """Return the station with the given station ID, if it exists."""
    return next((station for station in stations if station.id == station_id), None)


class StationListUnavailableError(Exception):
    """Error to indicate the NMBS station list cannot be fetched."""


async def async_fetch_stations(hass: HomeAssistant) -> list[StationDetails]:
    """Fetch the list of NMBS stations from the iRail API."""
    api_client = IRail(session=async_get_clientsession(hass))
    try:
        response = await api_client.get_stations()
    except (PyRailError, TimeoutError, ValueError, LookupError) as err:
        raise StationListUnavailableError from err
    if response is None:
        raise StationListUnavailableError
    return response.stations


class NMBSCoordinator(DataUpdateCoordinator[NMBSData]):
    """Coordinator to fetch NMBS connection and liveboard data."""

    config_entry: NMBSConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NMBSConfigEntry,
        stations: list[StationDetails],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = IRail(session=async_get_clientsession(hass))
        station_from = _find_station(stations, entry.data[CONF_STATION_FROM])
        station_to = _find_station(stations, entry.data[CONF_STATION_TO])
        if station_from is None or station_to is None:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="station_not_found",
            )
        self.station_from = station_from
        self.station_to = station_to
        self.exclude_vias = entry.data.get(CONF_EXCLUDE_VIAS, False)
        self._connection_response: ConnectionsApiResponse | None = None
        self._liveboard_responses: dict[str, LiveboardApiResponse] = {}
        self._failed_feeds: set[str] = set()

    async def _async_fetch_feed[T](
        self, fetch: Callable[[], Awaitable[T | None]]
    ) -> FeedResult[T]:
        """Fetch one feed and keep the error when the request fails."""
        try:
            return FeedResult(await fetch(), None)
        except (PyRailError, TimeoutError, ValueError, LookupError) as err:
            return FeedResult(None, err)

    def _log_feed_changes(self, reasons: dict[str, str], names: dict[str, str]) -> None:
        """Log the feeds that became unavailable or recovered since the last refresh."""
        for feed in reasons.keys() - self._failed_feeds:
            _LOGGER.info("Unable to fetch %s: %s", names[feed], reasons[feed])
        for feed in (self._failed_feeds - reasons.keys()) & names.keys():
            _LOGGER.info("Recovered feed: %s", names[feed])
        self._failed_feeds = set(reasons)

    def _connection_entity_enabled(self, entries: list[er.RegistryEntry]) -> bool:
        """Return True if the connection entity is enabled or not registered."""
        connection_entries = [
            entry
            for entry in entries
            if entry.unique_id.startswith(CONNECTION_UNIQUE_ID_PREFIX)
        ]
        return not connection_entries or any(
            entry.disabled_by is None for entry in connection_entries
        )

    def _liveboard_entity_enabled(
        self, station: StationDetails, entries: list[er.RegistryEntry]
    ) -> bool:
        """Return True if the liveboard entity for the station is enabled."""
        prefix = f"{LIVEBOARD_UNIQUE_ID_PREFIX}{station.id}_"
        return any(
            entry.disabled_by is None and entry.unique_id.startswith(prefix)
            for entry in entries
        )

    @override
    async def _async_update_data(self) -> NMBSData:
        """Fetch the connection and liveboard departures for enabled entities."""
        entries = er.async_entries_for_config_entry(
            er.async_get(self.hass), self.config_entry.entry_id
        )
        stations = [
            station
            for station in (self.station_from, self.station_to)
            if self._liveboard_entity_enabled(station, entries)
        ]
        fetch_connection = self._connection_entity_enabled(entries)
        names = {
            station.id: f"the liveboard of {station.standard_name}"
            for station in stations
        }
        if fetch_connection:
            names[CONNECTION_FEED] = (
                f"the connection from {self.station_from.standard_name}"
                f" to {self.station_to.standard_name}"
            )
        async with asyncio.TaskGroup() as task_group:
            connection_task = (
                task_group.create_task(
                    self._async_fetch_feed(
                        partial(
                            self.client.get_connections,
                            self.station_from.id,
                            self.station_to.id,
                        ),
                    )
                )
                if fetch_connection
                else None
            )
            liveboard_tasks = {
                station.id: task_group.create_task(
                    self._async_fetch_feed(
                        partial(self.client.get_liveboard, station_id=station.id)
                    )
                )
                for station in stations
            }
        reasons: dict[str, str] = {}
        if connection_task is not None:
            connection_result = connection_task.result()
            if connection_result.error is not None:
                reasons[CONNECTION_FEED] = _error_reason(connection_result.error)
            elif connection_result.data is not None:
                self._connection_response = connection_result.data
            elif self._connection_response is None:
                reasons[CONNECTION_FEED] = "no data"

        connections_response = self._connection_response

        upcoming: list[ConnectionDetails] = []
        if connections_response is not None:
            upcoming = [
                connection
                for connection in connections_response.connections
                if not connection.departure.left
            ]
            if self.exclude_vias:
                upcoming = [
                    connection for connection in upcoming if not connection.vias
                ]

        next_departures: dict[str, LiveboardDeparture | None] = {}
        for station in (self.station_from, self.station_to):
            if (liveboard_task := liveboard_tasks.get(station.id)) is None:
                next_departures[station.id] = None
                continue
            liveboard_result = liveboard_task.result()
            if liveboard_result.error is not None:
                reasons[station.id] = _error_reason(liveboard_result.error)
            elif liveboard_result.data is not None:
                self._liveboard_responses[station.id] = liveboard_result.data
            liveboard = self._liveboard_responses.get(station.id)
            if liveboard is None or liveboard.departures is None:
                reasons.setdefault(station.id, "no departures")
                next_departures[station.id] = None
                continue
            next_departures[station.id] = (
                liveboard.departures[0] if liveboard.departures else None
            )

        self._log_feed_changes(reasons, names)
        return NMBSData(
            connection=upcoming[0] if upcoming else None,
            next_departures=next_departures,
            failed_feeds=set(reasons),
        )


def _error_reason(err: Exception) -> str:
    """Return a readable reason for a failed request."""
    return str(err) or type(err).__name__
