"""The coordinator for the Youless integration."""

from datetime import timedelta
import logging

from youless_api import YoulessAPI

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class YouLessCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching YouLess data."""

    def __init__(self, hass: HomeAssistant, device: YoulessAPI) -> None:
        """Initialize global YouLess data provider."""
        super().__init__(
            hass, _LOGGER, name="youless_gateway", update_interval=timedelta(seconds=10)
        )
        self.device = device

    async def _async_update_data(self) -> None:
        await self.hass.async_add_executor_job(self.device.update)
