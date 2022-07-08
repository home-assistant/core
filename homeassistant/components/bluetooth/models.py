"""Models for bluetooth."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Final, cast

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData, AdvertisementDataCallback
from lru import LRU  # pylint: disable=no-name-in-module

from homeassistant.core import CALLBACK_TYPE, callback as hass_callback

_LOGGER = logging.getLogger(__name__)

FILTER_UUIDS: Final = "UUIDs"

HA_BLEAK_SCANNER: HaBleakScanner | None = None

MAX_HISTORY_SIZE: Final = 512


def _dispatch_callback(
    callback: AdvertisementDataCallback,
    filters: dict[str, set[str]],
    device: BLEDevice,
    advertisement_data: AdvertisementData,
) -> None:
    """Dispatch the callback."""
    if not callback:
        # Callback destroyed right before being called, ignore
        return

    if (uuids := filters.get(FILTER_UUIDS)) and not uuids.intersection(
        advertisement_data.service_uuids
    ):
        return

    try:
        callback(device, advertisement_data)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error in callback: %s", callback)


class HaBleakScanner(BleakScanner):  # type: ignore[misc]
    """BleakScanner that cannot be stopped."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the BleakScanner."""
        self._callbacks: list[
            tuple[AdvertisementDataCallback, dict[str, set[str]]]
        ] = []
        self._history: LRU = LRU(MAX_HISTORY_SIZE)
        super().__init__(*args, **kwargs)

    @hass_callback
    def async_register_callback(
        self, callback: AdvertisementDataCallback, filters: dict[str, set[str]]
    ) -> CALLBACK_TYPE:
        """Register a callback."""
        callback_entry = (callback, filters)
        self._callbacks.append(callback_entry)

        @hass_callback
        def _remove_callback() -> None:
            self._callbacks.remove(callback_entry)

        # Replay the history since otherwise we miss devices
        # that were already discovered before the callback was registered
        # or we are in passive mode
        for device, advertisement_data in self._history.values():
            _dispatch_callback(callback, filters, device, advertisement_data)

        return _remove_callback

    def async_callback_dispatcher(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Dispatch the callback.

        Here we get the actual callback from bleak and dispatch
        it to all the wrapped HaBleakScannerWrapper classes
        """
        self._history[device.address] = (device, advertisement_data)
        for callback_filters in self._callbacks:
            _dispatch_callback(*callback_filters, device, advertisement_data)


class HaBleakScannerWrapper(BleakScanner):  # type: ignore[misc]
    """A wrapper that uses the single instance."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the BleakScanner."""
        self._detection_cancel: CALLBACK_TYPE | None = None
        self._mapped_filters: dict[str, set[str]] = {}
        if "filters" in kwargs:
            self._mapped_filters = {k: set(v) for k, v in kwargs["filters"].items()}
        if "service_uuids" in kwargs:
            self._mapped_filters[FILTER_UUIDS] = set(kwargs["service_uuids"])
        super().__init__(*args, **kwargs)

    async def stop(self, *args: Any, **kwargs: Any) -> None:
        """Stop scanning for devices."""
        return

    async def start(self, *args: Any, **kwargs: Any) -> None:
        """Start scanning for devices."""
        return

    def _cancel_callback(self) -> None:
        """Cancel callback."""
        if self._detection_cancel:
            self._detection_cancel()
            self._detection_cancel = None

    @property
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""
        assert HA_BLEAK_SCANNER is not None
        return cast(list[BLEDevice], HA_BLEAK_SCANNER.discovered_devices)

    def register_detection_callback(self, callback: AdvertisementDataCallback) -> None:
        """Register a callback that is called when a device is discovered or has a property changed.

        This method takes the callback and registers it with the long running
        scanner.
        """
        self._cancel_callback()
        super().register_detection_callback(callback)
        assert HA_BLEAK_SCANNER is not None
        self._detection_cancel = HA_BLEAK_SCANNER.async_register_callback(
            self._callback, self._mapped_filters
        )

    def __del__(self) -> None:
        """Delete the BleakScanner."""
        if self._detection_cancel:
            # Nothing to do if event loop is already closed
            with contextlib.suppress(RuntimeError):
                asyncio.get_running_loop().call_soon_threadsafe(self._detection_cancel)
