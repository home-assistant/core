"""Sanix Coordinator."""

from datetime import timedelta
import logging

from sanix import Sanix
from sanix.exceptions import SanixException
from sanix.models import Measurement

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class SanixCoordinator(DataUpdateCoordinator[Measurement]):
    """Sanix coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, sanix_api: Sanix) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, _LOGGER, name=MANUFACTURER, update_interval=timedelta(hours=1)
        )
        self._sanix_api = sanix_api

    async def _async_update_data(self) -> Measurement:
        """Fetch data from API endpoint."""
        try:
            return await self.hass.async_add_executor_job(self._sanix_api.fetch_data)
        except SanixException as err:
            raise UpdateFailed("Error while communicating with the API") from err
