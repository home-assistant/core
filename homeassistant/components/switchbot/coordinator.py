"""Provides the switchbot DataUpdateCoordinator."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

import async_timeout
import switchbot

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant, callback

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice


_LOGGER = logging.getLogger(__name__)

DEVICE_STARTUP_TIMEOUT = 30


def flatten_sensors_data(sensor):
    """Deconstruct SwitchBot library temp object C/Fº readings from dictionary."""
    if "temp" in sensor["data"]:
        sensor["data"]["temperature"] = sensor["data"]["temp"]["c"]

    return sensor


class SwitchbotDataUpdateCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Class to manage fetching switchbot data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        ble_device: BLEDevice,
        device: switchbot.SwitchbotDevice,
        base_unique_id: str,
        device_name: str,
        connectable: bool,
        model: str,
    ) -> None:
        """Initialize global switchbot data updater."""
        super().__init__(
            hass,
            logger,
            ble_device.address,
            bluetooth.BluetoothScanningMode.ACTIVE,
            connectable,
        )
        self.ble_device = ble_device
        self.device = device
        self.data: dict[str, Any] = {}
        self.device_name = device_name
        self.base_unique_id = base_unique_id
        self.model = model
        self._ready_event = asyncio.Event()

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        self.ble_device = service_info.device
        if adv := switchbot.parse_advertisement_data(
            service_info.device, service_info.advertisement
        ):
            if "modelName" in self.data:
                self._ready_event.set()
            _LOGGER.debug("%s: Switchbot data: %s", self.ble_device.address, self.data)
            if not self.device.advertisement_changed(adv):
                return
            self.data = flatten_sensors_data(adv.data)
            self.device.update_from_advertisement(adv)
        super()._async_handle_bluetooth_event(service_info, change)

    async def async_wait_ready(self) -> bool:
        """Wait for the device to be ready."""
        with contextlib.suppress(asyncio.TimeoutError):
            async with async_timeout.timeout(DEVICE_STARTUP_TIMEOUT):
                await self._ready_event.wait()
                return True
        return False
