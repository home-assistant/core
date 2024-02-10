"""Sanix Coordinator."""
from datetime import timedelta
import logging

from sanix import Sanix
from sanix.exceptions import SanixException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_API_BATTERY,
    ATTR_API_DEVICE_NO,
    ATTR_API_DISTANCE,
    ATTR_API_FILL_PERCENTAGE,
    ATTR_API_SERVICE_DATE,
    ATTR_API_SSID,
    ATTR_API_STATUS,
    ATTR_API_TIME,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)


class SanixCoordinator(DataUpdateCoordinator):
    """Sanix coordinator."""

    def __init__(self, hass: HomeAssistant, sanix_api: Sanix) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, _LOGGER, name=MANUFACTURER, update_interval=timedelta(hours=1)
        )
        self._sanix_api = sanix_api

    async def _async_update_data(self) -> dict[str, str | float | int]:
        """Fetch data from API endpoint."""
        data: dict[str, str | float | int] = {}
        try:
            response = await self.hass.async_add_executor_job(
                self._sanix_api.fetch_data
            )
        except SanixException as err:
            raise UpdateFailed("Error while communicating with the API") from err

        data[ATTR_API_DEVICE_NO] = response.get("device_no")
        data[ATTR_API_STATUS] = response.get("status")
        data[ATTR_API_TIME] = response.get("time")
        data[ATTR_API_SSID] = response.get("ssid")
        data[ATTR_API_BATTERY] = response.get("battery")
        data[ATTR_API_DISTANCE] = response.get("distance")
        data[ATTR_API_FILL_PERCENTAGE] = response.get("fill_perc")
        data[ATTR_API_SERVICE_DATE] = response.get("service_date")
        return data
