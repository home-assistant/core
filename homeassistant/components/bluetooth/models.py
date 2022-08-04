"""Models for bluetooth."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any, Final

from bleak import BleakScanner
from bleak.backends.scanner import (
    AdvertisementData,
    AdvertisementDataCallback,
    BaseBleakScanner,
)

from homeassistant.core import CALLBACK_TYPE, callback as hass_callback

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice


_LOGGER = logging.getLogger(__name__)

FILTER_UUIDS: Final = "UUIDs"

HA_BLEAK_SCANNER: HaBleakScanner | None = None


def _dispatch_callback(
    callback: AdvertisementDataCallback,
    filters: dict[str, set[str]],
    device: BLEDevice,
    advertisement_data: AdvertisementData,
) -> None:
    """Dispatch the callback."""
    if not callback:
        # Callback destroyed right before being called, ignore
        return  # type: ignore[unreachable]

    if (uuids := filters.get(FILTER_UUIDS)) and not uuids.intersection(
        advertisement_data.service_uuids
    ):
        return

    try:
        callback(device, advertisement_data)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error in callback: %s", callback)


class HaBleakScanner(BleakScanner):
    """BleakScanner that cannot be stopped."""

    def __init__(  # pylint: disable=super-init-not-called
        self, *args: Any, **kwargs: Any
    ) -> None:
        """Initialize the BleakScanner."""
        self._callbacks: list[
            tuple[AdvertisementDataCallback, dict[str, set[str]]]
        ] = []
        self.history: dict[str, tuple[BLEDevice, AdvertisementData]] = {}
        # Init called later in async_setup if we are enabling the scanner
        # since init has side effects that can throw exceptions
        self._setup = False

    @hass_callback
    def async_setup(self, *args: Any, **kwargs: Any) -> None:
        """Deferred setup of the BleakScanner since __init__ has side effects."""
        if not self._setup:
            super().__init__(*args, **kwargs)
            self._setup = True

    @hass_callback
    def async_reset(self) -> None:
        """Reset the scanner so it can be setup again."""
        self.history = {}
        self._setup = False

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
        for device, advertisement_data in self.history.values():
            _dispatch_callback(callback, filters, device, advertisement_data)

        return _remove_callback

    def async_callback_dispatcher(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Dispatch the callback.

        Here we get the actual callback from bleak and dispatch
        it to all the wrapped HaBleakScannerWrapper classes
        """
        self.history[device.address] = (device, advertisement_data)
        for callback_filters in self._callbacks:
            _dispatch_callback(*callback_filters, device, advertisement_data)


class HaBleakScannerWrapper(BaseBleakScanner):
    """A wrapper that uses the single instance."""

    def __init__(
        self,
        *args: Any,
        detection_callback: AdvertisementDataCallback | None = None,
        service_uuids: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the BleakScanner."""
        self._detection_cancel: CALLBACK_TYPE | None = None
        self._mapped_filters: dict[str, set[str]] = {}
        self._adv_data_callback: AdvertisementDataCallback | None = None
        remapped_kwargs = {
            "detection_callback": detection_callback,
            "service_uuids": service_uuids or [],
            **kwargs,
        }
        self._map_filters(*args, **remapped_kwargs)
        super().__init__(
            detection_callback=detection_callback, service_uuids=service_uuids or []
        )

    async def stop(self, *args: Any, **kwargs: Any) -> None:
        """Stop scanning for devices."""

    async def start(self, *args: Any, **kwargs: Any) -> None:
        """Start scanning for devices."""

    def _map_filters(self, *args: Any, **kwargs: Any) -> bool:
        """Map the filters."""
        mapped_filters = {}
        if filters := kwargs.get("filters"):
            if filter_uuids := filters.get(FILTER_UUIDS):
                mapped_filters[FILTER_UUIDS] = set(filter_uuids)
            else:
                _LOGGER.warning("Only %s filters are supported", FILTER_UUIDS)
        if service_uuids := kwargs.get("service_uuids"):
            mapped_filters[FILTER_UUIDS] = set(service_uuids)
        if mapped_filters == self._mapped_filters:
            return False
        self._mapped_filters = mapped_filters
        return True

    def set_scanning_filter(self, *args: Any, **kwargs: Any) -> None:
        """Set the filters to use."""
        if self._map_filters(*args, **kwargs):
            self._setup_detection_callback()

    def _cancel_callback(self) -> None:
        """Cancel callback."""
        if self._detection_cancel:
            self._detection_cancel()
            self._detection_cancel = None

    @property
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""
        assert HA_BLEAK_SCANNER is not None
        return HA_BLEAK_SCANNER.discovered_devices

    def register_detection_callback(
        self, callback: AdvertisementDataCallback | None
    ) -> None:
        """Register a callback that is called when a device is discovered or has a property changed.

        This method takes the callback and registers it with the long running
        scanner.
        """
        self._adv_data_callback = callback
        self._setup_detection_callback()

    def _setup_detection_callback(self) -> None:
        """Set up the detection callback."""
        if self._adv_data_callback is None:
            return
        self._cancel_callback()
        super().register_detection_callback(self._adv_data_callback)
        assert HA_BLEAK_SCANNER is not None
        assert self._callback is not None
        self._detection_cancel = HA_BLEAK_SCANNER.async_register_callback(
            self._callback, self._mapped_filters
        )

    def __del__(self) -> None:
        """Delete the BleakScanner."""
        if self._detection_cancel:
            # Nothing to do if event loop is already closed
            with contextlib.suppress(RuntimeError):
                asyncio.get_running_loop().call_soon_threadsafe(self._detection_cancel)
