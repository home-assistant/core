"""DataUpdateCoordinator for Qube Heat Pump."""

from __future__ import annotations

from datetime import timedelta
import logging
import math
from typing import TYPE_CHECKING

from python_qube_heatpump.models import QubeState

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .hub import QubeHub

_LOGGER = logging.getLogger(__name__)

# Keys that require monotonic clamping (total_increasing sensors)
MONOTONIC_KEYS = frozenset(
    {
        "energy_total_electric",
        "energy_total_thermic",
    }
)


class QubeCoordinator(DataUpdateCoordinator[QubeState]):
    """Qube Heat Pump custom coordinator."""

    def __init__(self, hass: HomeAssistant, hub: QubeHub, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hub = hub
        self.entry = entry
        self._previous_values: dict[str, float] = {}
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
        if not self.hub.is_connected:
            await self.hub.async_connect()

        try:
            data = await self.hub.async_get_all_data()
        except Exception as exc:
            raise UpdateFailed(f"Error communicating with API: {exc}") from exc

        if data is None:
            raise UpdateFailed("Error communicating with API: No data received")

        # Apply monotonic clamping for total_increasing sensors
        self._apply_monotonic_clamping(data)

        return data

    def _apply_monotonic_clamping(self, data: QubeState) -> None:
        """Apply monotonic clamping to prevent energy statistic corruption.

        The Qube heat pump occasionally reports glitched values that are lower
        than previously reported totals. For total_increasing sensors, this
        would corrupt Home Assistant's energy statistics.

        This method preserves the previous valid value when a lower value
        is reported.
        """
        for key in MONOTONIC_KEYS:
            current_value = getattr(data, key, None)
            if current_value is None:
                continue

            # Skip non-finite values
            if not math.isfinite(current_value):
                _LOGGER.debug(
                    "Skipping non-finite value for %s: %s", key, current_value
                )
                continue

            previous_value = self._previous_values.get(key)
            if previous_value is not None and current_value < previous_value:
                _LOGGER.debug(
                    "Monotonic clamp: %s reported %s but previous was %s, keeping %s",
                    key,
                    current_value,
                    previous_value,
                    previous_value,
                )
                # Set the attribute back to the previous value
                object.__setattr__(data, key, previous_value)
            else:
                # Update the stored previous value
                self._previous_values[key] = current_value
