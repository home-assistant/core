"""The coordinator for Hypontech Cloud integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from hyponcloud import HyponCloud, OverviewData, PlantData, RequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


@dataclass
class HypontechCoordinatorData:
    """Store coordinator data."""

    overview: OverviewData
    plants: dict[str, PlantData]


type HypontechConfigEntry = ConfigEntry[HypontechDataCoordinator]


class HypontechDataCoordinator(DataUpdateCoordinator[HypontechCoordinatorData]):
    """Coordinator used for all sensors."""

    config_entry: HypontechConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HypontechConfigEntry,
        api: HyponCloud,
        account_id: str,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Hypontech Data",
            update_interval=timedelta(seconds=60),
        )
        self.api = api
        self.account_id = account_id

    async def _async_update_data(self) -> HypontechCoordinatorData:
        try:
            overview = await self.api.get_overview()
            plants = await self.api.get_list()
        except RequestError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="connection_error"
            ) from ex
        return HypontechCoordinatorData(
            overview=overview,
            plants={plant.plant_id: plant for plant in plants},
        )
