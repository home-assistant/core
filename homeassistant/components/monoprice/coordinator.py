"""Coordinator for Monoprice Amplifier."""
from __future__ import annotations

from datetime import timedelta
import logging

from pymonoprice import Monoprice, ZoneStatus
from serial import SerialException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=10)


class MonopriceDataUpdateCoordinator(DataUpdateCoordinator[dict[int, ZoneStatus]]):
    """DataUpdateCoordinator to query zone information for Monoprice Amplifier."""

    def __init__(
        self, hass: HomeAssistant, monoprice: Monoprice, zones: list[int]
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific zones."""
        super().__init__(
            hass,
            _LOGGER,
            name="Monoprice",
            update_interval=POLL_INTERVAL,
        )
        self._monoprice = monoprice
        self._zones = zones

    async def _async_update_data(self) -> dict[int, ZoneStatus]:
        """Fetch data for each of the zones."""
        return await self.hass.async_add_executor_job(self._update_all_zones)

    def _update_all_zones(self) -> dict[int, ZoneStatus]:
        """Fetch data for each of the zones."""
        data = {}
        for zone_id in self._zones:
            try:
                zone_status = self._monoprice.zone_status(zone_id)
            except SerialException as exc:
                if zone_id < 20:
                    raise UpdateFailed(f"Failed to update zone {zone_id}") from exc
            else:
                if zone_status:
                    data[zone_id] = zone_status

        return data
