"""Data update coordinator for the NMBS integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from pyrail import iRail
from pyrail.models import ConnectionDetails, LiveboardDeparture, StationDetails

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_EXCLUDE_VIAS,
    CONF_STATION_FROM,
    CONF_STATION_TO,
    DOMAIN,
    NMBS_STATION_DATA,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)

type NMBSConfigEntry = ConfigEntry[NMBSCoordinator]


@dataclass
class NMBSData:
    """Data fetched by the NMBS coordinator."""

    connection: ConnectionDetails | None
    next_departures: dict[str, LiveboardDeparture | None]


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

    @override
    async def _async_update_data(self) -> NMBSData:
        """Fetch the next connection and liveboard departures."""
        try:
            connections_response = await self.client.get_connections(
                self.station_from.id, self.station_to.id
            )
            liveboard_from = await self.client.get_liveboard(self.station_from.id)
            liveboard_to = await self.client.get_liveboard(self.station_to.id)
        except TimeoutError as err:
            raise UpdateFailed(
                f"Timeout while fetching data from the iRail API: {err}"
            ) from err
        if (
            connections_response is None
            or liveboard_from is None
            or liveboard_to is None
        ):
            raise UpdateFailed("Unable to fetch data from the iRail API")

        upcoming = [
            connection
            for connection in connections_response.connections
            if not connection.departure.left
        ]
        if self.exclude_vias:
            upcoming = [connection for connection in upcoming if not connection.vias]

        return NMBSData(
            connection=upcoming[0] if upcoming else None,
            next_departures={
                self.station_from.id: (
                    liveboard_from.departures[0] if liveboard_from.departures else None
                ),
                self.station_to.id: (
                    liveboard_to.departures[0] if liveboard_to.departures else None
                ),
            },
        )
