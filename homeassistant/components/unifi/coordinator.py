"""UniFi Network data update coordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from aiounifi.interfaces.api_handlers import APIHandler

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER

if TYPE_CHECKING:
    from .hub.hub import UnifiHub

POLL_INTERVAL = timedelta(seconds=10)


class UnifiDataUpdateCoordinator[HandlerT: APIHandler](DataUpdateCoordinator[None]):
    """Coordinator managing polling for a single UniFi API data source."""

    def __init__(
        self,
        hub: UnifiHub,
        handler: HandlerT,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hub.hass,
            LOGGER,
            name=f"UniFi {type(handler).__name__}",
            config_entry=hub.config.entry,
            update_interval=POLL_INTERVAL,
        )
        self._handler = handler

    @property
    def handler(self) -> HandlerT:
        """Return the aiounifi handler managed by this coordinator."""
        return self._handler

    async def _async_update_data(self) -> None:
        """Update data from the API handler."""
        await self._handler.update()
