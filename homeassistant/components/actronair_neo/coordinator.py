"""Coordinator for Actron Air Neo integration."""

from datetime import timedelta
import logging

from actron_neo_api import ActronNeoAPI

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class ActronNeoDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Custom coordinator for Actron Air Neo integration."""

    def __init__(self, hass: HomeAssistant, pairing_token: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Actron Neo Status",
            update_interval=SCAN_INTERVAL,
        )

        self.api = ActronNeoAPI(pairing_token=pairing_token)

    async def _async_update_data(self) -> dict:
        """Fetch updates and merge incremental changes into the full state."""
        if self.api.access_token is None:
            await self.api.refresh_token()

        await self.api.update_status()

        return self.api.status
