"""DataUpdateCoordinator for QuickBars connectivity."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from quickbars_bridge.events import ws_ping

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class QuickBarsCoordinator(DataUpdateCoordinator[bool]):
    """Poll ws_ping periodically to determine connectivity."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"quickbars_{entry.entry_id}_conn",
            update_interval=timedelta(seconds=10),
        )
        self.entry = entry

    async def _async_update_data(self) -> bool:
        """Return True if device responds; raise UpdateFailed otherwise."""
        try:
            ok = await ws_ping(self.hass, self.entry, timeout=5.0)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            raise UpdateFailed(str(err)) from err

        if not ok:
            raise UpdateFailed("Device did not respond")

        return True
