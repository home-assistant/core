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
from bleak.backends.client import BaseBleakClient, get_platform_client_backend_type
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


@dataclass
class HaBluetoothConnector:
    """Data for how to connect a BLEDevice from a given scanner."""

    client: type[BaseBleakClient]
    source: str
    can_connect: Callable[[], bool]


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

    def __init__(  # pylint: disable=super-init-not-called, keyword-arg-before-vararg
        self,
        address_or_ble_device: str | BLEDevice,
        disconnected_callback: Callable[[BleakClient], None]
        | None = None,  # kwargs first to match parent
        *args: Any,
        timeout: float = 10.0,
        **kwargs: Any,
    ) -> None:
        """Initialize the BleakClient."""
        if isinstance(address_or_ble_device, BLEDevice):
            self.__address = address_or_ble_device.address
        else:
            report(
                "attempted to call BleakClient with an address instead of a BLEDevice",
                exclude_integrations={"bluetooth"},
                error_if_core=False,
            )
            self.__address = address_or_ble_device
        self.__disconnected_callback = disconnected_callback
        self.__timeout = timeout
        self._backend: BaseBleakClient | None = None

    @property
    def is_connected(self) -> bool:
        """Return True if the client is connected to a device."""
        return self._backend is not None and self._backend.is_connected

    def set_disconnected_callback(
        self, callback: Callable[[BaseBleakClient], None] | None, **kwargs: Any
    ) -> None:
        """Set the disconnect callback.

        The callback will only be called on unsolicited disconnect event.

        Callbacks must accept one input which is the client object itself.

        Set the callback to ``None`` to remove any existing callback.

        .. code-block:: python

            def callback(client):
                print("Client with address {} got disconnected!".format(client.address))

            client.set_disconnected_callback(callback)
            client.connect()

        Args:
            callback: callback to be called on disconnection.

        """
        self.__disconnected_callback = callback
        if self._backend:
            self._backend.set_disconnected_callback(callback, **kwargs)

    async def connect(self, **kwargs: Any) -> bool:
        """Connect to the specified GATT server.

        Args:
            **kwargs: For backwards compatibility - should not be used.
        Returns:
            Always returns ``True`` for backwards compatibility.
        """
        self._backend = self._get_backend()
        return await super().connect(**kwargs)

    def _get_backend_for_ble_device(
        self, ble_device: BLEDevice
    ) -> BaseBleakClient | None:
        """Get the backend for a BLEDevice."""
        details = ble_device.details
        if not isinstance(details, dict) or "connector" not in details:
            # If client is not defined in details
            # its the client for this platform
            cls = get_platform_client_backend_type()
            return cls(
                ble_device,
                disconnected_callback=self.__disconnected_callback,
                timeout=self.__timeout,
            )

        connector: HaBluetoothConnector = details["connector"]
        # Make sure the backend can connect to the device
        # as some backends have connection limits
        if not connector.can_connect():
            return None

        return connector.client(
            ble_device,
            disconnected_callback=self.__disconnected_callback,
            timeout=self.__timeout,
        )

    def _get_backend(self) -> BaseBleakClient:
        """Get the bleak backend for the given address."""
        assert MANAGER is not None
        address = self.__address
        ble_device = MANAGER.async_ble_device_from_address(address, True)
        if ble_device is None:
            raise BleakError(f"No device found for address {address}")

        if backend := self._get_backend_for_ble_device(ble_device):
            return backend

        #
        # The preferred backend cannot currently connect the device
        # because it is likely out of connection slots.
        #
        # We need to try all backends to find one that can
        # connect to the device.
        #
        # Currently we have to search all the discovered devices
        # because the bleak API does not allow us to get the
        # details for a specific device.
        #
        for ble_device in sorted(
            (
                ble_device
                for ble_device in MANAGER.async_all_discovered_devices(True)
                if ble_device.address == address
            ),
            key=lambda ble_device: ble_device.rssi or -1000,
            reverse=True,
        ):
            if backend := self._get_backend_for_ble_device(ble_device):
                return backend

        raise BleakError(
            f"No backend with an available connection slot that can reach address {address} was found"
        )

    async def disconnect(self) -> bool:
        """Disconnect from the device."""
        if self._backend is None:
            return True
        return await self._backend.disconnect()
