"""DataUpdateCoordinator for Qube Heat Pump."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from python_qube_heatpump.models import QubeState

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .hub import QubeHub

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class QubeCoordinator(DataUpdateCoordinator[QubeState]):
    """Qube Heat Pump custom coordinator."""

    def __init__(self, hass: HomeAssistant, hub: QubeHub, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hub = hub
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name="qube_heatpump_coordinator",
            update_method=self._async_update_data,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )

    async def _async_update_data(self) -> QubeState:
        """Fetch data from the hub."""
        # Ensure connection
        if not self.hub.client.is_connected:
            await self.hub.async_connect()

        try:
            data = await self.hub.async_get_all_data()
        except Exception as exc:
            raise UpdateFailed(f"Error communicating with API: {exc}") from exc

        if data is None:
            raise UpdateFailed("Error communicating with API: No data received")

        # Note: Previous implementation handled monotonic counters for specific keys.
        # If the library handles raw values, we might need to re-implement monotonicity
        # for total_increasing sensors if the device resets them.
        # For now, assuming library/device handles this or we accept raw values.

        return data
