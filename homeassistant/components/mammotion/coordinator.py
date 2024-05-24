"""Provides the mammotion DataUpdateCoordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from pyluba.mammotion.devices import MammotionBaseBLEDevice

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

MOWER_SCAN_INTERVAL = timedelta(minutes=1)
_LOGGER = logging.getLogger(__name__)

DEVICE_STARTUP_TIMEOUT = 30


class MammotionDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching mammotion data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        ble_device: BLEDevice,
        device: MammotionBaseBLEDevice,
        base_unique_id: str,
        device_name: str,
    ) -> None:
        """Initialize global mammotion data updater."""
        super().__init__(
            hass=hass,
            logger=logger,
            name="Mammotion Lawn Mower data",
            update_interval=MOWER_SCAN_INTERVAL,
        )
        self.ble_device = ble_device
        self.device = device
        self.device_name = device_name
        self.base_unique_id = base_unique_id
        self._was_unavailable = True

    async def _async_update_data(self) -> dict:
        """Poll the device."""
        if bool(
            bluetooth.async_ble_device_from_address(
                self.hass, self.ble_device.address, connectable=True
            )
        ):
            return await self.device.start_sync("key", 0)

        return self.device.raw_data
