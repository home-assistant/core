"""The coordinator for Hypontech Cloud integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from hyponcloud import ConnectionError as HyponConnectionError, HyponCloud, OverviewData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import HypontechConfigEntry


@dataclass
class HypontechSensorData:
    """Representing different Hypontech sensor data.

    It contains only OverviewData for now, but Hypontech has other kind of data like PlantData that we plan to add support later.
    """

    overview_data: OverviewData


@dataclass
class HypontechData:
    """Store runtime data."""

    coordinator: HypontechDataCoordinator


class HypontechDataCoordinator(DataUpdateCoordinator[HypontechSensorData]):
    """Coordinator used for all sensors."""

    config_entry: HypontechConfigEntry
    api: HyponCloud

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
        except HyponConnectionError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="connection_error"
            ) from ex
        return HypontechSensorData(overview_data=data)
