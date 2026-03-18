"""DataUpdateCoordinator for Qube Heat Pump."""

from __future__ import annotations

from datetime import timedelta
import logging
import math
from typing import TYPE_CHECKING

from python_qube_heatpump import QubeClient
from python_qube_heatpump.models import QubeState

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

MONOTONIC_KEYS = frozenset({"energy_total_electric", "energy_total_thermic"})


class QubeCoordinator(DataUpdateCoordinator[QubeState]):
    """Qube Heat Pump data coordinator."""

    def __init__(
        self, hass: HomeAssistant, client: QubeClient, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self._previous_values: dict[str, float] = {}
        super().__init__(
            hass,
            _LOGGER,
            name="qube_heatpump",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )

    async def _async_update_data(self) -> QubeState:
        """Fetch data from the device."""
        try:
            data = await self.client.get_all_data()
        except (ConnectionError, TimeoutError, OSError) as exc:
            raise UpdateFailed(
                f"Error communicating with Qube heat pump: {exc}"
            ) from exc

        if data is None:
            raise UpdateFailed("No data received from Qube heat pump")

        self._apply_monotonic_clamping(data)
        return data

    def _apply_monotonic_clamping(self, data: QubeState) -> None:
        """Prevent total_increasing sensors from decreasing due to glitches."""
        for key in MONOTONIC_KEYS:
            current = getattr(data, key, None)
            if current is None or not math.isfinite(current):
                continue
            previous = self._previous_values.get(key)
            if previous is not None and current < previous:
                setattr(data, key, previous)
            else:
                self._previous_values[key] = current
