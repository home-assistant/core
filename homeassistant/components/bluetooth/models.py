"""Models for bluetooth."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable
import contextlib
from dataclasses import dataclass
from enum import Enum
import logging
from typing import TYPE_CHECKING, Any, Final

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import (
    AdvertisementData,
    AdvertisementDataCallback,
    BaseBleakScanner,
)

from homeassistant.core import CALLBACK_TYPE
from homeassistant.helpers.frame import report
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

if TYPE_CHECKING:

    from .manager import BluetoothManager


_LOGGER = logging.getLogger(__name__)

FILTER_UUIDS: Final = "UUIDs"

MANAGER: BluetoothManager | None = None


@dataclass
class BluetoothServiceInfoBleak(BluetoothServiceInfo):
    """BluetoothServiceInfo with bleak data.

    Integrations may need BLEDevice and AdvertisementData
    to connect to the device without having bleak trigger
    another scan to translate the address to the system's
    internal details.
    """

    device: BLEDevice
    advertisement: AdvertisementData
    connectable: bool
    time: float


class BluetoothScanningMode(Enum):
    """The mode of scanning for bluetooth devices."""

    PASSIVE = "passive"
    ACTIVE = "active"


BluetoothChange = Enum("BluetoothChange", "ADVERTISEMENT")
BluetoothCallback = Callable[[BluetoothServiceInfoBleak, BluetoothChange], None]
ProcessAdvertisementCallback = Callable[[BluetoothServiceInfoBleak], bool]


class BaseHaScanner:
    """Base class for Ha Scanners."""

    @property
    @abstractmethod
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""

    async def async_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the scanner."""
        return {
            "type": self.__class__.__name__,
            "discovered_devices": [
                {
                    "name": device.name,
                    "address": device.address,
                    "rssi": device.rssi,
                }
                for device in self.discovered_devices
            ],
        }


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
        self._advertisement_data_callback: AdvertisementDataCallback | None = None
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
        assert MANAGER is not None
        return list(MANAGER.async_discovered_devices(True))

    def register_detection_callback(
        self, callback: AdvertisementDataCallback | None
    ) -> None:
        """Register a callback that is called when a device is discovered or has a property changed.

        This method takes the callback and registers it with the long running
        scanner.
        """
        self._advertisement_data_callback = callback
        self._setup_detection_callback()

    def _setup_detection_callback(self) -> None:
        """Set up the detection callback."""
        if self._advertisement_data_callback is None:
            return
        self._cancel_callback()
        super().register_detection_callback(self._advertisement_data_callback)
        assert MANAGER is not None
        assert self._callback is not None
        self._detection_cancel = MANAGER.async_register_bleak_callback(
            self._callback, self._mapped_filters
        )

    def __del__(self) -> None:
        """Delete the BleakScanner."""
        if self._detection_cancel:
            # Nothing to do if event loop is already closed
            with contextlib.suppress(RuntimeError):
                asyncio.get_running_loop().call_soon_threadsafe(self._detection_cancel)


class HaBleakClientWrapper(BleakClient):
    """Wrap the BleakClient to ensure it does not shutdown our scanner.

    If an address is passed into BleakClient instead of a BLEDevice,
    bleak will quietly start a new scanner under the hood to resolve
    the address. This can cause a conflict with our scanner. We need
    to handle translating the address to the BLEDevice in this case
    to avoid the whole stack from getting stuck in an in progress state
    when an integration does this.
    """

    def __init__(
        self, address_or_ble_device: str | BLEDevice, *args: Any, **kwargs: Any
    ) -> None:
        """Initialize the BleakClient."""
        if isinstance(address_or_ble_device, BLEDevice):
            super().__init__(address_or_ble_device, *args, **kwargs)
            return
        report(
            "attempted to call BleakClient with an address instead of a BLEDevice",
            exclude_integrations={"bluetooth"},
            error_if_core=False,
        )
        assert MANAGER is not None
        ble_device = MANAGER.async_ble_device_from_address(address_or_ble_device, True)
        if ble_device is None:
            raise BleakError(f"No device found for address {address_or_ble_device}")
        super().__init__(ble_device, *args, **kwargs)
