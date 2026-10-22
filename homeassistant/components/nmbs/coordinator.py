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
    failed: bool


def _find_station(
    stations: list[StationDetails], station_id: str
) -> StationDetails | None:
    """Return the station with the given station ID, if it exists."""
    return next((station for station in stations if station.id == station_id), None)


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
        self, feed: str, fetch: Callable[[], Awaitable[T | None]]
    ) -> FeedResult[T]:
        """Fetch one feed and record whether the request failed."""
        try:
            result = await fetch()
        except (PyRailError, TimeoutError, ValueError, LookupError) as err:
            if feed not in self._failed_feeds:
                _LOGGER.warning("Unable to fetch %s: %s", feed, err)
            self._failed_feeds.add(feed)
            return FeedResult(None, True)
        if feed in self._failed_feeds:
            _LOGGER.info("Recovered feed: %s", feed)
            self._failed_feeds.remove(feed)
        return FeedResult(result, False)

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
        async with asyncio.TaskGroup() as task_group:
            connection_task = (
                task_group.create_task(
                    self._async_fetch_feed(
                        f"the connection from {self.station_from.standard_name}"
                        f" to {self.station_to.standard_name}",
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
                        f"the liveboard of {station.standard_name}",
                        partial(self.client.get_liveboard, station_id=station.id),
                    )
                )
                for station in stations
            }
        failed_feeds: set[str] = set()
        if connection_task is not None:
            connection_result = connection_task.result()
            if connection_result.failed:
                failed_feeds.add(CONNECTION_FEED)
            elif connection_result.data is not None:
                self._connection_response = connection_result.data
            elif self._connection_response is None:
                failed_feeds.add(CONNECTION_FEED)

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
            if liveboard_result.failed:
                failed_feeds.add(station.id)
            elif liveboard_result.data is not None:
                self._liveboard_responses[station.id] = liveboard_result.data
            elif station.id not in self._liveboard_responses:
                failed_feeds.add(station.id)
                next_departures[station.id] = None
                continue
            liveboard = self._liveboard_responses.get(station.id)
            if liveboard is None or liveboard.departures is None:
                failed_feeds.add(station.id)
                next_departures[station.id] = None
                continue
            next_departures[station.id] = (
                liveboard.departures[0] if liveboard.departures else None
            )

        return NMBSData(
            connection=upcoming[0] if upcoming else None,
            next_departures=next_departures,
            failed_feeds=failed_feeds,
        )
