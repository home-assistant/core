"""DataUpdateCoordinator for steamist."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiosteamist import Steamist, SteamistStatus

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

REQUEST_REFRESH_DELAY = 2.5


class SteamistDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data from a steamist steam shower."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Steamist,
        host: str,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific steamist."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=f"Steamist {host}",
            update_interval=timedelta(seconds=5),
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self) -> SteamistStatus:
        """Fetch data from steamist."""
        return await self.client.async_get_status()
