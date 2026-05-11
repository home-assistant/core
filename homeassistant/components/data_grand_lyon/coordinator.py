"""DataUpdateCoordinator for the Data Grand Lyon integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from aiohttp import ClientResponseError
from data_grand_lyon_ha import DataGrandLyonClient, TclPassage, VelovStation

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_LINE,
    CONF_STATION_ID,
    CONF_STOP_ID,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_STOP,
    SUBENTRY_TYPE_VELOV_STATION,
)

type DataGrandLyonConfigEntry = ConfigEntry[DataGrandLyonCoordinator]


@dataclass
class DataGrandLyonCoordinatorData:
    """Data returned by the coordinator."""

    stops: dict[str, list[TclPassage]]
    velov_stations: dict[str, VelovStation]


class DataGrandLyonCoordinator(DataUpdateCoordinator[DataGrandLyonCoordinatorData]):
    """Coordinator for the Data Grand Lyon integration."""

    config_entry: DataGrandLyonConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: DataGrandLyonConfigEntry,
        client: DataGrandLyonClient,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> DataGrandLyonCoordinatorData:
        """Fetch data for all monitored stops and Vélo'v stations."""
        stop_subentries = list(
            self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_STOP)
        )
        velov_subentries = list(
            self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_VELOV_STATION)
        )

        stop_tasks = [
            self.client.get_tcl_passages(
                ligne=subentry.data[CONF_LINE],
                stop_id=subentry.data[CONF_STOP_ID],
            )
            for subentry in stop_subentries
        ]

        velov_tasks = [
            self.client.get_velov_station(
                station_id=subentry.data[CONF_STATION_ID],
            )
            for subentry in velov_subentries
        ]

        stop_results: list[list[TclPassage] | BaseException] = await asyncio.gather(
            *stop_tasks, return_exceptions=True
        )
        velov_results: list[VelovStation | None | BaseException] = await asyncio.gather(
            *velov_tasks, return_exceptions=True
        )

        total_subentries = len(stop_subentries) + len(velov_subentries)
        success_count = 0

        stops: dict[str, list[TclPassage]] = {}
        for i, subentry in enumerate(stop_subentries):
            result = stop_results[i]
            if isinstance(result, BaseException):
                self._handle_error(result, subentry.subentry_id)
                continue
            stops[subentry.subentry_id] = result
            success_count += 1

        velov_stations: dict[str, VelovStation] = {}
        for i, subentry in enumerate(velov_subentries):
            velov_result = velov_results[i]
            if isinstance(velov_result, BaseException):
                self._handle_error(velov_result, subentry.subentry_id)
                continue
            success_count += 1
            if velov_result is not None:
                velov_stations[subentry.subentry_id] = velov_result
            else:
                LOGGER.warning(
                    "Vélo'v station not found for subentry %s",
                    subentry.subentry_id,
                )

        if total_subentries and not success_count:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_all",
            )
        return DataGrandLyonCoordinatorData(stops=stops, velov_stations=velov_stations)

    def _handle_error(self, error: BaseException, subentry_id: str) -> None:
        """Handle an error from a single subentry fetch."""
        if isinstance(error, ClientResponseError) and error.status in (401, 403):
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from error
        LOGGER.warning(
            "Error fetching data for subentry %s: %s",
            subentry_id,
            error,
        )
