"""DataUpdateCoordinator for the Data Grand Lyon integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta

from data_grand_lyon_ha import DataGrandLyonClient, TclPassage, VelovStation

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_LINE,
    CONF_STATION_ID,
    CONF_STOP_ID,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_STOP,
    SUBENTRY_TYPE_VELOV,
)

type DataGrandLyonConfigEntry = ConfigEntry[DataGrandLyonCoordinator]


@dataclass
class DataGrandLyonData:
    """Aggregated data from the Data Grand Lyon coordinator."""

    stops: dict[str, list[TclPassage]] = field(default_factory=dict)
    velov: dict[str, VelovStation | None] = field(default_factory=dict)


class DataGrandLyonCoordinator(DataUpdateCoordinator[DataGrandLyonData]):
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
            update_interval=timedelta(minutes=1),
        )

    async def _async_update_data(self) -> DataGrandLyonData:
        """Fetch data for all monitored stops and stations."""
        stop_subentries = list(
            self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_STOP)
        )
        velov_subentries = list(
            self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_VELOV)
        )

        stop_tasks = [
            self.client.get_tcl_passages(
                ligne=subentry.data[CONF_LINE],
                stop_id=subentry.data[CONF_STOP_ID],
            )
            for subentry in stop_subentries
        ]
        velov_tasks = [
            self.client.get_velov_station(subentry.data[CONF_STATION_ID])
            for subentry in velov_subentries
        ]

        stop_results: list[list[TclPassage] | BaseException] = await asyncio.gather(
            *stop_tasks, return_exceptions=True
        )
        velov_results: list[VelovStation | None | BaseException] = await asyncio.gather(
            *velov_tasks, return_exceptions=True
        )

        stops: dict[str, list[TclPassage]] = {}
        for i, subentry in enumerate(stop_subentries):
            result = stop_results[i]
            if isinstance(result, BaseException):
                LOGGER.warning(
                    "Error fetching passages for stop %s: %s",
                    subentry.subentry_id,
                    result,
                )
                continue
            stops[subentry.subentry_id] = result

        velov: dict[str, VelovStation | None] = {}
        for i, subentry in enumerate(velov_subentries):
            velov_result = velov_results[i]
            if isinstance(velov_result, BaseException):
                LOGGER.warning(
                    "Error fetching Vélo'v station %s: %s",
                    subentry.subentry_id,
                    velov_result,
                )
                continue
            velov[subentry.subentry_id] = velov_result

        if (stop_subentries or velov_subentries) and not stops and not velov:
            raise UpdateFailed("Error fetching DataGrandLyon data: all requests failed")
        return DataGrandLyonData(stops=stops, velov=velov)
