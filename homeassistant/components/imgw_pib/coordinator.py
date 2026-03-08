"""Data Update Coordinator for IMGW-PIB integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from imgw_pib import ApiError, HydrologicalData, ImgwPib

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class ImgwPibData:
    """Data for the IMGW-PIB integration."""

    coordinator: ImgwPibDataUpdateCoordinator


type ImgwPibConfigEntry = ConfigEntry[ImgwPibData]


class ImgwPibDataUpdateCoordinator(DataUpdateCoordinator[HydrologicalData]):
    """Class to manage fetching IMGW-PIB data API."""

    config_entry: ImgwPibConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ImgwPibConfigEntry,
        imgwpib: ImgwPib,
        station_id: str,
    ) -> None:
        """Initialize."""
        self.imgwpib = imgwpib
        self.station_id = station_id
        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, station_id)},
            manufacturer="IMGW-PIB",
            name=f"{imgwpib.hydrological_stations[station_id]}",
            configuration_url=f"https://hydro.imgw.pl/#/station/hydro/{station_id}",
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> HydrologicalData:
        """Update data via internal method."""
        try:
            return await self.imgwpib.get_hydrological_data()
        except ApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={
                    "entry": self.config_entry.title,
                    "error": repr(err),
                },
            ) from err
