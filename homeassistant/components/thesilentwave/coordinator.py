"""Coordinator for TheSilentWave integration."""

from datetime import timedelta
import logging

from pysilentwave import SilentWaveClient
from pysilentwave.exceptions import SilentWaveError

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class TheSilentWaveCoordinator(DataUpdateCoordinator):
    """Class to manage fetching the data from the API."""

    def __init__(self, hass, name, host, scan_interval):
        """Initialize the coordinator."""
        self._name = name
        self._client = SilentWaveClient(host)
        
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self):
        """Fetch data from the API."""
        try:
            status = await self._client.get_status()
            return status
        except SilentWaveError as err:
            raise UpdateFailed(f"Error fetching data from API: {err}") from err
