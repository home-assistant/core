"""Coordinator for Actron Air Neo integration."""

from datetime import timedelta
import logging
from typing import Any

from actron_neo_api import ActronNeoAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

type ActronConfigEntry = ConfigEntry[ActronNeoDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class ActronNeoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Custom coordinator for Actron Air Neo integration."""

    def __init__(
        self, hass: HomeAssistant, entry: ActronConfigEntry, pairing_token: str
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Actron Neo Status",
            update_interval=SCAN_INTERVAL,
        )
        self.api = ActronNeoAPI(pairing_token=pairing_token)
        self.entry = entry

    async def _async_setup(self) -> None:
        """Perform initial setup, including refreshing the token."""
        await self.api.refresh_token()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch updates and merge incremental changes into the full state."""
        await self.api.update_status()
        return self.api.status
