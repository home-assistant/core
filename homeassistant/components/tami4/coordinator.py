"""Water quality coordinator for Tami4Edge."""
from datetime import timedelta
import logging

from Tami4EdgeAPI import Tami4EdgeAPI

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class Tami4EdgeWaterQualityCoordinator(DataUpdateCoordinator):
    """Tami4Edge water quality coordinator."""

    def __init__(self, hass: HomeAssistant, edge: Tami4EdgeAPI) -> None:
        """Initialize the water quality coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Tami4Edge water quality coordinator",
            update_interval=timedelta(minutes=10),
        )
        self.edge = edge

    async def _async_update_data(self) -> dict:
        """Fetch data from the API endpoint."""
        try:
            water_quality = await self.hass.async_add_executor_job(
                self.edge.get_water_quality
            )
            return {
                "uv_last_replacement": water_quality.uv.last_replacement,
                "uv_upcoming_replacement": water_quality.uv.upcoming_replacement,
                "uv_status": water_quality.uv.status,
                "filter_last_replacement": water_quality.filter.last_replacement,
                "filter_upcoming_replacement": water_quality.filter.upcoming_replacement,
                "filter_status": water_quality.filter.status,
                "filter_milli_litters_passed": water_quality.filter.milli_litters_passed,
            }
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with API: {ex}") from ex
