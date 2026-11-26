"""Data update coordinator for Spain fuel prices (Geoportal Gasolineras)."""

from collections import defaultdict
import logging
from typing import override

from aioprecioscarburantes import PreciosCarburantes, PreciosCarburantesError, Station

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MUNICIPALITY_ID,
    CONF_STATION_ID,
    DOMAIN,
    SCAN_INTERVAL,
    SUBENTRY_TYPE_STATION,
)

_LOGGER = logging.getLogger(__name__)

type GeoportalGasolinerasConfigEntry = ConfigEntry[GeoportalGasolinerasCoordinator]


class GeoportalGasolinerasCoordinator(DataUpdateCoordinator[dict[str, Station]]):
    """Fetch the prices of all configured fuel stations."""

    config_entry: GeoportalGasolinerasConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: GeoportalGasolinerasConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = PreciosCarburantes(session=async_get_clientsession(hass))

    @override
    async def _async_update_data(self) -> dict[str, Station]:
        """Fetch the stations, one request per municipality.

        A municipality that cannot be fetched is left out, so only the entities of
        its stations become unavailable.
        """
        by_municipality: defaultdict[str, set[str]] = defaultdict(set)
        for subentry in self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_STATION):
            by_municipality[subentry.data[CONF_MUNICIPALITY_ID]].add(
                subentry.data[CONF_STATION_ID]
            )

        stations: dict[str, Station] = {}
        failed = 0
        for municipality_id, station_ids in by_municipality.items():
            try:
                result = await self.client.get_stations_by_municipality(municipality_id)
            except PreciosCarburantesError as err:
                _LOGGER.debug("Cannot fetch municipality %s: %s", municipality_id, err)
                failed += 1
                continue
            stations.update(
                (station.id, station)
                for station in result.stations
                if station.id in station_ids
            )

        if failed and failed == len(by_municipality):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            )
        return stations
