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

    uv_last_replacement: date
    uv_upcoming_replacement: date
    uv_status: str
    filter_last_replacement: date
    filter_upcoming_replacement: date
    filter_status: str
    filter_litters_passed: float

    def __init__(self, water_quality: WaterQuality) -> None:
        """Flatten WaterQuality dataclass."""

        self.uv_last_replacement = water_quality.uv.last_replacement
        self.uv_upcoming_replacement = water_quality.uv.upcoming_replacement
        self.uv_status = water_quality.uv.status
        self.filter_last_replacement = water_quality.filter.last_replacement
        self.filter_upcoming_replacement = water_quality.filter.upcoming_replacement
        self.filter_status = water_quality.filter.status
        self.filter_litters_passed = water_quality.filter.milli_litters_passed / 1000


class Tami4EdgeWaterQualityCoordinator(DataUpdateCoordinator[FlattenedWaterQuality]):
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
            water_quality = await self.hass.async_add_executor_job(
                self._api.get_water_quality
            )

            return FlattenedWaterQuality(water_quality)
        except exceptions.APIRequestFailedException as ex:
            raise UpdateFailed("Error communicating with API") from ex
