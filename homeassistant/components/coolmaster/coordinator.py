"""DataUpdateCoordinator for coolmaster integration."""
import logging

from homeassistant.components.climate import SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class CoolmasterDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Coolmaster data."""

    def __init__(self, hass, coolmaster):
        """Initialize global Coolmaster data updater."""
        self._coolmaster = coolmaster

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from Coolmaster."""
        try:
            return await self._coolmaster.status()
        except OSError as error:
            raise UpdateFailed from error
