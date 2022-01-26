"""DataUpdateCoordinator for steamist."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiosteamist import Steamist, SteamistStatus

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class SteamistDataUpdateCoordinator(DataUpdateCoordinator[SteamistStatus]):
    """DataUpdateCoordinator to gather data from a steamist steam shower."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Steamist,
        host: str,
        device_name: str | None,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific steamist."""
        self.client = client
        self.device_name = device_name
        super().__init__(
            hass,
            _LOGGER,
            name=f"Steamist {host}",
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self) -> SteamistStatus:
        """Fetch data from steamist."""
        return await self.client.async_get_status()
