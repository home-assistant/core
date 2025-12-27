"""The coordinator for Hypontech Cloud integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from hyponcloud import HyponCloud, OverviewData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


@dataclass
class HypontechSensorData:
    """Representing different Hypontech sensor data."""

    # plant_data: PlantData
    overview_data: OverviewData


@dataclass
class HypontechData:
    """Store runtime data."""

    coordinator: HypontechDataCoordinator
    device_id: str


type HypontechConfigEntry = ConfigEntry[HypontechData]


class HypontechDataCoordinator(DataUpdateCoordinator[HypontechSensorData]):
    """Coordinator used for all sensors."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HypontechConfigEntry,
        api: HyponCloud,
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

    async def _async_update_data(self) -> HypontechSensorData:
        try:
            data = await self.api.get_overview()
        except Exception:  # noqa: BLE001
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_error"
            ) from None
        return HypontechSensorData(overview_data=data)
