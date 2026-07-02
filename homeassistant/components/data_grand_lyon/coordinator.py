"""DataUpdateCoordinator for the Data Grand Lyon integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import override

from aiohttp import ClientError, ClientResponseError
from data_grand_lyon_ha import (
    DataGrandLyonClient,
    TclParkAndRide,
    TclPassage,
    VelovStation,
    extract_tcl_pictogram_from_zip,
    filter_tcl_passages_by_lines_stops,
    find_tcl_line_pictogram_by_code,
    find_tcl_park_and_ride_by_id,
    find_velov_stations_by_ids,
    sort_tcl_passages_by_time,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_LINE,
    CONF_PARK_ID,
    CONF_STATION_ID,
    CONF_STOP_ID,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_PARK_AND_RIDE,
    SUBENTRY_TYPE_STOP,
    SUBENTRY_TYPE_VELOV_STATION,
)


@dataclass
class DataGrandLyonData:
    """Runtime data for the Data Grand Lyon integration."""

    tcl_coordinator: DataGrandLyonTclCoordinator
    velov_coordinator: DataGrandLyonVelovCoordinator
    park_and_ride_coordinator: DataGrandLyonParkAndRideCoordinator
    pictogram_coordinator: DataGrandLyonPictogramCoordinator


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

    @override
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

    @override
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


class DataGrandLyonParkAndRideCoordinator(
    DataUpdateCoordinator[dict[str, TclParkAndRide]]
):
    """Coordinator for TCL park-and-ride (P+R) facilities."""

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
            name=f"{DOMAIN}_park_and_ride",
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> dict[str, TclParkAndRide]:
        """Fetch data for all monitored park-and-ride facilities."""
        park_subentries = list(
            self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_PARK_AND_RIDE)
        )
        if not park_subentries:
            return {}

        try:
            all_parks = await self.client.get_tcl_park_and_rides()
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed",
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_park_and_ride",
            ) from err
        except (ClientError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_park_and_ride",
            ) from err

        parks: dict[str, TclParkAndRide] = {}
        for subentry in park_subentries:
            park = find_tcl_park_and_ride_by_id(all_parks, subentry.data[CONF_PARK_ID])
            if park is not None:
                parks[subentry.subentry_id] = park
            else:
                LOGGER.warning(
                    "Park-and-ride not found for subentry %s",
                    subentry.subentry_id,
                )
        return parks


class DataGrandLyonPictogramCoordinator(DataUpdateCoordinator[dict[str, bytes]]):
    """Coordinator for TCL line pictograms (SVG images).

    Pictograms are a best-effort bonus: a failure here only makes the image
    entities unavailable and never blocks the rest of the integration, so this
    coordinator never raises ConfigEntryAuthFailed.
    """

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
            name=f"{DOMAIN}_pictograms",
            update_interval=timedelta(days=1),
        )

    async def _async_update_data(self) -> dict[str, bytes]:
        """Fetch and extract the line pictogram for each monitored stop."""
        stop_subentries = list(
            self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_STOP)
        )
        if not stop_subentries:
            return {}

        try:
            lines = await self.client.get_tcl_line_pictograms()
            zip_bytes = await self.client.get_tcl_line_pictograms_zip()
        except (ClientError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_pictograms",
            ) from err

        pictograms: dict[str, bytes] = {}
        for subentry in stop_subentries:
            line = subentry.data[CONF_LINE]
            picto = find_tcl_line_pictogram_by_code(lines, line)
            svg = (
                extract_tcl_pictogram_from_zip(zip_bytes, picto.picto_complet)
                if picto is not None
                else None
            )
            if svg is not None:
                pictograms[subentry.subentry_id] = svg
            else:
                LOGGER.warning(
                    "No pictogram found for line %s (subentry %s)",
                    line,
                    subentry.subentry_id,
                )
        return pictograms
