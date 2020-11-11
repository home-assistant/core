"""Ruckus Unleashed DataUpdateCoordinator."""
from datetime import timedelta
import logging

from pyruckus import Ruckus
from pyruckus.exceptions import AuthenticationError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_CLIENTS,
    API_CURRENT_ACTIVE_CLIENTS,
    API_MAC,
    DOMAIN,
    SCAN_INTERVAL,
)

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

    async def _fetch_clients(self) -> dict:
        """Fetch clients from the API and format them."""
        clients = await self.hass.async_add_executor_job(
            self.ruckus.current_active_clients
        )
        return {e[API_MAC]: e for e in clients[API_CURRENT_ACTIVE_CLIENTS][API_CLIENTS]}

    async def _async_update_data(self) -> dict:
        """Fetch Ruckus Unleashed data."""
        try:
            return {API_CLIENTS: await self._fetch_clients()}
        except (AuthenticationError, ConnectionError) as error:
            raise UpdateFailed(error) from error
