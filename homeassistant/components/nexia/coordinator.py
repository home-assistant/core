"""Component to embed nexia devices."""
from __future__ import annotations

from datetime import timedelta
import logging

from nexia.home import NexiaHome

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_RATE = 120


class NexiaDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """DataUpdateCoordinator for nexia homes."""

    def __init__(
        self,
        hass: HomeAssistant,
        nexia_home: NexiaHome,
    ) -> None:
        """Initialize DataUpdateCoordinator for the nexia home."""
        self.nexia_home = nexia_home
        super().__init__(
            hass,
            _LOGGER,
            name="Nexia update",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_RATE),
        )

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        return await self.nexia_home.update()
