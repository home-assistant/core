"""Models for bluetooth."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData, AdvertisementDataCallback

from homeassistant.core import CALLBACK_TYPE, callback as hass_callback

_LOGGER = logging.getLogger(__name__)


class HaBleakScanner(BleakScanner):
    """BleakScanner that cannot be stopped."""

    _callbacks: list[AdvertisementDataCallback] = []

    @hass_callback
    def async_register_callback(
        self, callback: AdvertisementDataCallback
    ) -> CALLBACK_TYPE:
        """Register a callback."""
        self._callbacks.append(callback)

        @hass_callback
        def _remove_callback():
            self._callbacks.remove(callback)

        return _remove_callback

    def async_callback_disptacher(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Dispatch the callback.

        Here we get the actual callback from bleak and dispatch
        it to all the wrapped HaBleakScannerWrapper classes
        """
        for callback in self._callbacks:
            try:
                callback(device, advertisement_data)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error in callback: %s", callback)


class HaBleakScannerWrapper(BleakScanner):
    """A wrapper that uses the single instance."""

    _ha_bleak_scanner: HaBleakScanner
    _detection_cancel: CALLBACK_TYPE | None

    async def stop(self, *args: Any, **kwargs: Any) -> None:
        """Stop scanning for devices."""
        return

    async def start(self, *args: Any, **kwargs: Any) -> None:
        """Start scanning for devices."""
        return

    def _cancel_callback(self):
        """Cancel callback."""
        if self._detection_cancel:
            self._detection_cancel()
            self._detection_cancel = None

    def register_detection_callback(self, callback: AdvertisementDataCallback) -> None:
        """Register a callback that is called when a device is discovered or has a property changed.

        This method takes the callback and registers it with the long running
        scanner.
        """
        self._cancel_callback()
        super().register_detection_callback(callback)
        self._detection_cancel = self._ha_bleak_scanner.async_register_callback(
            self._callback
        )

    def __del__(self):
        """Delete the BleakScanner."""
        if self._detection_cancel:
            asyncio.get_running_loop().call_soon_threadsafe(self._detection_cancel)
