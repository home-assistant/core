"""Data update coordinator for the NMBS integration."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
import logging
from typing import TypeVar, override

from pyrail import iRail
from pyrail.models import ConnectionDetails, LiveboardDeparture, StationDetails

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
    NMBS_STATION_DATA,
)

_LOGGER = logging.getLogger(__name__)

ApiResponseT = TypeVar("ApiResponseT")

UPDATE_INTERVAL = timedelta(seconds=60)

type NMBSConfigEntry = ConfigEntry[NMBSCoordinator]


@dataclass
class NMBSData:
    """Data fetched by the NMBS coordinator."""

    connection: ConnectionDetails | None
    next_departures: dict[str, LiveboardDeparture | None]
    failed_feeds: set[str]


def _find_station(hass: HomeAssistant, station_id: str) -> StationDetails | None:
    """Return the station with the given station ID, if it exists."""
    return next(
        (
            station
            for station in hass.data[NMBS_STATION_DATA]
            if station.id == station_id
        ),
        None,
    )


class NMBSCoordinator(DataUpdateCoordinator[NMBSData]):
    """Coordinator to fetch NMBS connection and liveboard data."""

    config_entry: NMBSConfigEntry

    def __init__(self, hass: HomeAssistant, entry: NMBSConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = iRail(session=async_get_clientsession(hass))
        station_from = _find_station(hass, entry.data[CONF_STATION_FROM])
        station_to = _find_station(hass, entry.data[CONF_STATION_TO])
        if station_from is None or station_to is None:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="station_not_found",
            )
        self.station_from = station_from
        self.station_to = station_to
        self.exclude_vias = entry.data.get(CONF_EXCLUDE_VIAS, False)

    async def _async_fetch_feed(
        self, feed: str, fetch: Callable[[], Awaitable[ApiResponseT | None]]
    ) -> ApiResponseT | None:
        """Fetch a feed, returning None when the request fails."""
        try:
            return await fetch()
        except TimeoutError:
            _LOGGER.debug("Timeout while fetching %s", feed)
            return None
        except (ValueError, LookupError) as err:
            _LOGGER.debug("Unable to parse %s: %s", feed, err)
            return None

    def _config_entry_entities(self) -> list[er.RegistryEntry]:
        """Return the entity registry entries of this config entry."""
        return er.async_entries_for_config_entry(
            er.async_get(self.hass), self.config_entry.entry_id
        )

    def _connection_entity_enabled(self) -> bool:
        """Return True if the connection entity is enabled or not yet registered."""
        entries = self._config_entry_entities()
        return not entries or any(
            entry.disabled_by is None
            and entry.unique_id.startswith(CONNECTION_UNIQUE_ID_PREFIX)
            for entry in entries
        )

    def _liveboard_entity_enabled(self, station: StationDetails) -> bool:
        """Return True if the liveboard entity for the station is enabled."""
        prefix = f"{LIVEBOARD_UNIQUE_ID_PREFIX}{station.id}_"
        return any(
            entry.disabled_by is None and entry.unique_id.startswith(prefix)
            for entry in self._config_entry_entities()
        )

    @override
    async def _async_update_data(self) -> NMBSData:
        """Fetch the next connection and the departures of enabled liveboards."""
        stations = [
            station
            for station in (self.station_from, self.station_to)
            if self._liveboard_entity_enabled(station)
        ]
        fetch_connection = self._connection_entity_enabled()
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
                        partial(self.client.get_liveboard, station.id),
                    )
                )
                for station in stations
            }
        connections_response = (
            connection_task.result() if connection_task is not None else None
        )
        failed_feeds: set[str] = set()
        if fetch_connection and connections_response is None:
            failed_feeds.add(CONNECTION_FEED)

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
            liveboard = liveboard_task.result()
            if liveboard is None:
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
