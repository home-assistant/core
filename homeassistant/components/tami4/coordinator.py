"""Water quality coordinator for Tami4Edge."""

from dataclasses import dataclass
from datetime import date, timedelta
import logging

from Tami4EdgeAPI import Tami4EdgeAPI, exceptions
from Tami4EdgeAPI.water_quality import WaterQuality

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


@dataclass
class FlattenedWaterQuality:
    """Flattened WaterQuality dataclass."""

    uv_upcoming_replacement: date
    uv_installed: bool
    filter_upcoming_replacement: date
    filter_installed: bool
    filter_litters_passed: float

    def __init__(self, water_quality: WaterQuality) -> None:
        """Flattened WaterQuality dataclass."""

        self.uv_upcoming_replacement = water_quality.uv.upcoming_replacement
        self.uv_installed = water_quality.uv.installed
        self.filter_upcoming_replacement = water_quality.filter.upcoming_replacement
        self.filter_installed = water_quality.filter.installed
        self.filter_litters_passed = water_quality.filter.milli_litters_passed / 1000


class Tami4EdgeCoordinator(DataUpdateCoordinator[FlattenedWaterQuality]):
    """Tami4Edge water quality coordinator."""

    def __init__(self, hass: HomeAssistant, api: Tami4EdgeAPI) -> None:
        """Initialize the water quality coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Tami4Edge water quality coordinator",
            update_interval=timedelta(minutes=60),
        )
        self._api = api

    async def _async_update_data(self) -> FlattenedWaterQuality:
        """Fetch data from the API endpoint."""
        try:
            device = await self.hass.async_add_executor_job(self._api.get_device)

            return FlattenedWaterQuality(device.water_quality)
        except exceptions.APIRequestFailedException as ex:
            raise UpdateFailed("Error communicating with API") from ex
