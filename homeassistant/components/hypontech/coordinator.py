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
        # Enabled entities register a context so we only call the matching API:
        # the account ID for overview sensors, the plant ID for plant monitor
        # sensors. On the first refresh no entity is registered yet, so fetch
        # everything to populate the sensors without delay.
        first_refresh = self.data is None
        wanted = set(self.async_contexts())
        try:
            if first_refresh or self.account_id in wanted:
                overview = await self.api.get_overview()
            else:
                overview = OverviewData()
            plants = await self.api.get_list()
            monitored = [
                plant for plant in plants if first_refresh or plant.plant_id in wanted
            ]
            monitors = await asyncio.gather(
                *(self.api.get_monitor(plant.plant_id) for plant in monitored)
            )
        except RequestError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="connection_error"
            ) from ex
        monitor_by_id = {
            plant.plant_id: monitor
            for plant, monitor in zip(monitored, monitors, strict=True)
        }
        return HypontechCoordinatorData(
            overview=overview,
            plants={
                plant.plant_id: HypontechPlant(
                    info=plant,
                    monitor=monitor_by_id.get(plant.plant_id, PlantMonitorData()),
                )
                for plant in plants
            },
        )
