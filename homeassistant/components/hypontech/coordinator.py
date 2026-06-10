"""The coordinator for Hypontech Cloud integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from hyponcloud import (
    HyponCloud,
    OverviewData,
    PlantData,
    PlantMonitorData,
    RequestError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


@dataclass
class HypontechPlant:
    """Store a plant together with its real-time monitor data."""

    info: PlantData
    monitor: PlantMonitorData


@dataclass
class HypontechCoordinatorData:
    """Store coordinator data."""

    overview: OverviewData
    plants: dict[str, HypontechPlant]


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
            monitors = await asyncio.gather(
                *(self.api.get_monitor(plant.plant_id) for plant in plants)
            )
        except RequestError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="connection_error"
            ) from ex
        return HypontechCoordinatorData(
            overview=overview,
            plants={
                plant.plant_id: HypontechPlant(info=plant, monitor=monitor)
                for plant, monitor in zip(plants, monitors, strict=True)
            },
        )
