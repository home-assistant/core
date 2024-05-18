"""Provides the mammotion DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

import pyluba

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import CoreState, HomeAssistant, callback

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice


_LOGGER = logging.getLogger(__name__)

DEVICE_STARTUP_TIMEOUT = 30


class MammotionDataUpdateCoordinator(ActiveBluetoothDataUpdateCoordinator[None]):
    """Class to manage fetching mammotion data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        ble_device: BLEDevice,
        device: mammotion.MammotionLubaDevice,
        base_unique_id: str,
        device_name: str
    ) -> None:
        """Initialize global mammotion data updater."""
        super().__init__(
            hass=hass,
            logger=logger,
            address=ble_device.address,
            needs_poll_method=self._needs_poll,
            poll_method=self._async_update,
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=True,
        )
        self.ble_device = ble_device
        self.device = device
        self.device_name = device_name
        self.base_unique_id = base_unique_id
        self._ready_event = asyncio.Event()
        self._was_unavailable = True

    @callback
    def _needs_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        seconds_since_last_poll: float | None,
    ) -> bool:
        # Only poll if hass is running, we need to poll,
        # and we actually have a way to connect to the device
        return (
            self.hass.state is CoreState.running
            and self.device.poll_needed(seconds_since_last_poll)
            and bool(
                bluetooth.async_ble_device_from_address(
                    self.hass, service_info.device.address, connectable=True
                )
            )
        )

    async def _async_update(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Poll the device."""
        await self.device.start_sync()

    @callback
    def _async_handle_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Handle the device going unavailable."""
        super()._async_handle_unavailable(service_info)
        self._was_unavailable = True

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        self.ble_device = service_info.device
        if not (
            adv := mammotion.parse_advertisement_data(
                service_info.device, service_info.advertisement, self.model
            )
        ):
            return
        if "modelName" in adv.data:
            self._ready_event.set()
        _LOGGER.debug(
            "%s: mammotion Luba data: %s", self.ble_device.address, self.device.data
        )
        if not self.device.advertisement_changed(adv) and not self._was_unavailable:
            return
        self._was_unavailable = False
        self.device.update_from_advertisement(adv)
        super()._async_handle_bluetooth_event(service_info, change)

    async def async_wait_ready(self) -> bool:
        """Wait for the device to be ready."""
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(DEVICE_STARTUP_TIMEOUT):
                await self._ready_event.wait()
                return True
        return False
