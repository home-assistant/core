"""DataUpdateCoordinator for Mitsubishi Comfort devices."""

from __future__ import annotations

import logging

from mitsubishi_comfort import IndoorUnit, KumoStation

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MitsubishiComfortCoordinator(DataUpdateCoordinator[IndoorUnit | KumoStation]):
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
        self.data = device

    async def _async_update_data(self) -> IndoorUnit | KumoStation:
        """Poll the device and return it."""
        try:
            success = await self.device.update_status()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with {self.device.name}") from err
        if not success:
            raise UpdateFailed(f"Device {self.device.name} returned no data")
        return self.device
