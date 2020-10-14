"""Ruckus Unleashed DataUpdateCoordinator."""
from datetime import timedelta
import logging

from pyruckus import Ruckus
from pyruckus.exceptions import AuthenticationError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CLIENTS, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__package__)


class RuckusUnleashedDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data from Ruckus Unleashed client."""

    def __init__(self, hass: HomeAssistant, *, ruckus: Ruckus):
        """Initialize global Ruckus Unleashed data updater."""
        self.ruckus = ruckus

        update_interval = timedelta(seconds=SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict:
        """Fetch Ruckus Unleashed data."""
        try:
            return {
                CLIENTS: await self.hass.async_add_executor_job(self.ruckus.clients)
            }
        except (AuthenticationError, ConnectionError) as error:
            raise UpdateFailed(error) from error
