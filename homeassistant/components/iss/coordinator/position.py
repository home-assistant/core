"""DataUpdateCoordinator for ISS position; calculated from TLE data."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from skyfield.api import EarthSatellite, load
from skyfield.toposlib import wgs84

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from .tle import IssTleCoordinator

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)


class IssPositionCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Coordinator that calculates ISS position from TLE data.

    This coordinator uses Skyfield to calculate the current position of the ISS
    based on TLE data. Since position calculation is local (no API calls), we can
    update frequently. The update interval is user-configurable.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config_entry: ConfigEntry,
        tle_coordinator: IssTleCoordinator,
        update_interval: timedelta = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize the ISS position coordinator.

        Args:
            hass: Home Assistant instance.
            config_entry: The config entry for this integration.
            tle_coordinator: The TLE coordinator providing orbital data.
            update_interval: Frequency at which position is calculated.
        """
        self._tle_coordinator = tle_coordinator

        super().__init__(
            hass,
            _LOGGER,
            name="ISS Position",
            update_interval=update_interval,
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> dict[str, str]:
        """Calculate the current ISS position from TLE data."""
        # Get TLE data from the TLE coordinator

        tle_data = self._tle_coordinator.data
        if not tle_data or "line1" not in tle_data or "line2" not in tle_data:
            raise UpdateFailed("TLE data not available")

        def calculate_position() -> dict[str, str]:
            ts = load.timescale()
            t = ts.now()

            # Use the TLE lines directly
            line1 = tle_data["line1"]
            line2 = tle_data["line2"]

            _LOGGER.debug("TLE lines for ISS: %r / %r", line1, line2)

            # Create satellite object
            try:
                iss = EarthSatellite(line1, line2, "ISS (ZARYA)", ts)
            except ValueError as e:
                raise UpdateFailed(f"Failed to parse TLE lines: {e}") from e

            # Calculate position
            try:
                geocentric = iss.at(t)
                subpoint = wgs84.subpoint(geocentric)
            except ValueError as e:
                raise UpdateFailed(f"Failed to compute ISS position: {e}") from e

            _LOGGER.debug(
                "Coords: latitude=%s, longitude=%s",
                subpoint.latitude.degrees,
                subpoint.longitude.degrees,
            )
            return {
                "latitude": str(subpoint.latitude.degrees),
                "longitude": str(subpoint.longitude.degrees),
            }

        try:
            return await self.hass.async_add_executor_job(calculate_position)
        except Exception as err:
            raise UpdateFailed(f"Error calculating position: {err}") from err
