"""Data update coordinator for the openSenseMap integration."""

from dataclasses import dataclass
from datetime import timedelta

from opensensemap_api import OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(minutes=10)


@dataclass(slots=True, frozen=True)
class OpenSenseMapStationData:
    """Immutable measurements for an openSenseMap station."""

    pm2_5: float | None
    pm10: float | None


type OpenSenseMapConfigEntry = ConfigEntry[OpenSenseMapCoordinator]


class OpenSenseMapCoordinator(DataUpdateCoordinator[OpenSenseMapStationData]):
    """Coordinator to manage data updates for an openSenseMap station."""

    config_entry: OpenSenseMapConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OpenSenseMapConfigEntry,
        api: OpenSenseMap,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> OpenSenseMapStationData:
        """Fetch latest data from the openSenseMap API."""
        try:
            await self.api.get_data()
        except OpenSenseMapError as err:
            raise UpdateFailed(
                f"Unable to fetch data from openSenseMap: {err}"
            ) from err
        return OpenSenseMapStationData(pm2_5=self.api.pm2_5, pm10=self.api.pm10)
