"""DataUpdateCoordinator for Mitsubishi Comfort devices."""

from __future__ import annotations

import logging

from mitsubishi_comfort import IndoorUnit, KumoStation

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

MAX_FAILURES_BEFORE_UNAVAILABLE = 3


class MitsubishiComfortCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to poll a single Mitsubishi device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: IndoorUnit | KumoStation,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"mitsubishi_comfort_{device.serial}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.device = device
        self._consecutive_failures = 0

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self._consecutive_failures < MAX_FAILURES_BEFORE_UNAVAILABLE

    async def _async_update_data(self) -> None:
        success = await self.device.update_status()
        if success:
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
            _LOGGER.warning(
                "Device %s poll failed (%d consecutive)",
                self.device.name,
                self._consecutive_failures,
            )
            if self._consecutive_failures >= MAX_FAILURES_BEFORE_UNAVAILABLE:
                raise UpdateFailed(
                    f"Device {self.device.name} unavailable after "
                    f"{self._consecutive_failures} failures"
                )
