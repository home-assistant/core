"""DataUpdateCoordinator for the Data Grand Lyon integration."""

from dataclasses import dataclass
from datetime import timedelta

from aiohttp import ClientError, ClientResponseError
from data_grand_lyon_ha import (
    DataGrandLyonClient,
    TclPassage,
    VelovStation,
    filter_tcl_passages_by_lines_stops,
    find_velov_stations_by_ids,
    sort_tcl_passages_by_time,
)

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


@dataclass
class DataGrandLyonData:
    """Runtime data for the Data Grand Lyon integration."""

    tcl_coordinator: DataGrandLyonTclCoordinator
    velov_coordinator: DataGrandLyonVelovCoordinator


type DataGrandLyonConfigEntry = ConfigEntry[DataGrandLyonData]


class DataGrandLyonTclCoordinator(DataUpdateCoordinator[dict[str, list[TclPassage]]]):
    """Coordinator for TCL transit passages."""

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
            name=f"{DOMAIN}_tcl",
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> dict[str, list[TclPassage]]:
        """Fetch data for all monitored stops."""
        stop_subentries = list(
            self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_STOP)
        )
        if not stop_subentries:
            return {}

        try:
            all_passages = await self.client.get_tcl_passages()
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed",
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_tcl",
            ) from err
        except (ClientError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_tcl",
            ) from err

        lines_stops = [
            (subentry.data[CONF_LINE], subentry.data[CONF_STOP_ID])
            for subentry in stop_subentries
        ]
        grouped = filter_tcl_passages_by_lines_stops(all_passages, lines_stops)
        stops: dict[str, list[TclPassage]] = {}
        for subentry in stop_subentries:
            key = (subentry.data[CONF_LINE], subentry.data[CONF_STOP_ID])
            sorted_passages = sort_tcl_passages_by_time(grouped[key])
            if sorted_passages:
                stops[subentry.subentry_id] = sorted_passages
            else:
                LOGGER.warning(
                    "No TCL passages found for subentry %s",
                    subentry.subentry_id,
                )
        return stops


class DataGrandLyonVelovCoordinator(DataUpdateCoordinator[dict[str, VelovStation]]):
    """Coordinator for Vélo'v stations."""

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
            name=f"{DOMAIN}_velov",
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> dict[str, VelovStation]:
        """Fetch data for all monitored Vélo'v stations."""
        velov_subentries = list(
            self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_VELOV_STATION)
        )
        if not velov_subentries:
            return {}

        try:
            all_stations = await self.client.get_velov_stations()
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed",
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_velov",
            ) from err
        except (ClientError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_velov",
            ) from err

        station_ids = [subentry.data[CONF_STATION_ID] for subentry in velov_subentries]
        found = find_velov_stations_by_ids(all_stations, station_ids)
        velov_stations: dict[str, VelovStation] = {}
        for subentry in velov_subentries:
            station = found[subentry.data[CONF_STATION_ID]]
            if station is not None:
                velov_stations[subentry.subentry_id] = station
            else:
                LOGGER.warning(
                    "Vélo'v station not found for subentry %s",
                    subentry.subentry_id,
                )
        return velov_stations
