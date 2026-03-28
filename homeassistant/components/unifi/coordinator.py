"""UniFi Network data update coordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from aiounifi.interfaces.api_handlers import APIHandler

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER

if TYPE_CHECKING:
    from . import UnifiConfigEntry
    from .hub.hub import UnifiHub

POLL_INTERVAL = timedelta(seconds=10)


class UnifiDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator managing polling for a single UniFi API data source."""

    def __init__(
        self,
        hub: UnifiHub,
        config_entry: UnifiConfigEntry,
        handler: APIHandler,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hub.hass,
            LOGGER,
            name=f"UniFi {type(handler).__name__}",
            config_entry=config_entry,
            update_method=self._async_update,
            update_interval=POLL_INTERVAL,
        )
        self._handler = handler

    async def _async_update(self) -> None:
        """Update data from the API handler."""
        await self._handler.update()
