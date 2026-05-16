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

        has_stops = bool(stop_subentries)
        has_velov = bool(velov_subentries)
        stops: dict[str, list[TclPassage]] = {}
        velov_stations: dict[str, VelovStation] = {}
        tcl_success = not has_stops
        velov_success = not has_velov

        if has_stops:
            try:
                all_passages = await self.client.get_tcl_passages()
            except ClientResponseError as err:
                if err.status in (401, 403):
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN,
                        translation_key="auth_failed",
                    ) from err
                LOGGER.warning("Error fetching TCL passages: %s", err)
            except (ClientError, TimeoutError) as err:
                LOGGER.warning("Error fetching TCL passages: %s", err)
            else:
                tcl_success = True
                lines_stops = [
                    (subentry.data[CONF_LINE], subentry.data[CONF_STOP_ID])
                    for subentry in stop_subentries
                ]
                grouped = filter_tcl_passages_by_lines_stops(all_passages, lines_stops)
                for subentry in stop_subentries:
                    key = (subentry.data[CONF_LINE], subentry.data[CONF_STOP_ID])
                    stops[subentry.subentry_id] = sort_tcl_passages_by_time(
                        grouped[key]
                    )

        if has_velov:
            try:
                all_stations = await self.client.get_velov_stations()
            except ClientResponseError as err:
                if err.status in (401, 403):
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN,
                        translation_key="auth_failed",
                    ) from err
                LOGGER.warning("Error fetching Vélo'v stations: %s", err)
            except (ClientError, TimeoutError) as err:
                LOGGER.warning("Error fetching Vélo'v stations: %s", err)
            else:
                velov_success = True
                station_ids = [
                    subentry.data[CONF_STATION_ID] for subentry in velov_subentries
                ]
                found = find_velov_stations_by_ids(all_stations, station_ids)
                for subentry in velov_subentries:
                    station = found[subentry.data[CONF_STATION_ID]]
                    if station is not None:
                        velov_stations[subentry.subentry_id] = station
                    else:
                        LOGGER.warning(
                            "Vélo'v station not found for subentry %s",
                            subentry.subentry_id,
                        )

        if not tcl_success and not velov_success:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_all",
            )
        return DataGrandLyonCoordinatorData(stops=stops, velov_stations=velov_stations)
