"""Bleak wrappers for bluetooth."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
from dataclasses import dataclass
from functools import partial
import inspect
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
from bleak_retry_connector import (
    NO_RSSI_VALUE,
    ble_device_description,
    clear_cache,
    device_source,
)

from homeassistant.core import CALLBACK_TYPE, callback as hass_callback
from homeassistant.helpers.frame import report

from . import models
from .base_scanner import BaseHaScanner, BluetoothScannerDevice

FILTER_UUIDS: Final = "UUIDs"
_LOGGER = logging.getLogger(__name__)


if TYPE_CHECKING:
    from .manager import BluetoothManager


@dataclass(slots=True)
class _HaWrappedBleakBackend:
    """Wrap bleak backend to make it usable by Home Assistant."""

    device: BLEDevice
    scanner: BaseHaScanner
    client: type[BaseBleakClient]
    source: str | None


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
        self._background_tasks: set[asyncio.Task] = set()
        remapped_kwargs = {
            "detection_callback": detection_callback,
            "service_uuids": service_uuids or [],
            **kwargs,
        }
        self._map_filters(*args, **remapped_kwargs)
        super().__init__(
            detection_callback=detection_callback, service_uuids=service_uuids or []
        )

    @classmethod
    async def discover(cls, timeout: float = 5.0, **kwargs: Any) -> list[BLEDevice]:
        """Discover devices."""
        assert models.MANAGER is not None
        return list(models.MANAGER.async_discovered_devices(True))

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
        assert models.MANAGER is not None
        return list(models.MANAGER.async_discovered_devices(True))

    def register_detection_callback(
        self, callback: AdvertisementDataCallback | None
    ) -> Callable[[], None]:
        """Register a detection callback.

        The callback is called when a device is discovered or has a property changed.

        This method takes the callback and registers it with the long running scanner.
        """
        self._advertisement_data_callback = callback
        self._setup_detection_callback()
        assert self._detection_cancel is not None
        return self._detection_cancel

    def _setup_detection_callback(self) -> None:
        """Set up the detection callback."""
        if self._advertisement_data_callback is None:
            return
        callback = self._advertisement_data_callback
        self._cancel_callback()
        super().register_detection_callback(self._advertisement_data_callback)
        assert models.MANAGER is not None

        if not inspect.iscoroutinefunction(callback):
            detection_callback = callback
        else:

            def detection_callback(
                ble_device: BLEDevice, advertisement_data: AdvertisementData
            ) -> None:
                task = asyncio.create_task(callback(ble_device, advertisement_data))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)

        self._detection_cancel = models.MANAGER.async_register_bleak_callback(
            detection_callback, self._mapped_filters
        )

    def __del__(self) -> None:
        """Delete the BleakScanner."""
        if self._detection_cancel:
            # Nothing to do if event loop is already closed
            with contextlib.suppress(RuntimeError):
                asyncio.get_running_loop().call_soon_threadsafe(self._detection_cancel)


def _rssi_sorter_with_connection_failure_penalty(
    device: BluetoothScannerDevice,
    connection_failure_count: dict[BaseHaScanner, int],
    rssi_diff: int,
) -> float:
    """Get a sorted list of scanner, device, advertisement data.

    Adjusting for previous connection failures.

    When a connection fails, we want to try the next best adapter so we
    apply a penalty to the RSSI value to make it less likely to be chosen
    for every previous connection failure.

    We use the 51% of the RSSI difference between the first and second
    best adapter as the penalty. This ensures we will always try the
    best adapter twice before moving on to the next best adapter since
    the first failure may be a transient service resolution issue.
    """
    base_rssi = device.advertisement.rssi or NO_RSSI_VALUE
    if connect_failures := connection_failure_count.get(device.scanner):
        if connect_failures > 1 and not rssi_diff:
            rssi_diff = 1
        return base_rssi - (rssi_diff * connect_failures * 0.51)
    return base_rssi


class HaBleakClientWrapper(BleakClient):
    """Wrap the BleakClient to ensure it does not shutdown our scanner.

    If an address is passed into BleakClient instead of a BLEDevice,
    bleak will quietly start a new scanner under the hood to resolve
    the address. This can cause a conflict with our scanner. We need
    to handle translating the address to the BLEDevice in this case
    to avoid the whole stack from getting stuck in an in progress state
    when an integration does this.
    """

    def __init__(  # pylint: disable=super-init-not-called
        self,
        address_or_ble_device: str | BLEDevice,
        disconnected_callback: Callable[[BleakClient], None] | None = None,
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
        self.__connect_failures: dict[BaseHaScanner, int] = {}
        self._backend: BaseBleakClient | None = None  # type: ignore[assignment]

    @property
    def is_connected(self) -> bool:
        """Return True if the client is connected to a device."""
        return self._backend is not None and self._backend.is_connected

    async def clear_cache(self) -> bool:
        """Clear the GATT cache."""
        if self._backend is not None and hasattr(self._backend, "clear_cache"):
            return await self._backend.clear_cache()  # type: ignore[no-any-return]
        return await clear_cache(self.__address)

    def set_disconnected_callback(
        self,
        callback: Callable[[BleakClient], None] | None,
        **kwargs: Any,
    ) -> None:
        """Set the disconnect callback."""
        self.__disconnected_callback = callback
        if self._backend:
            self._backend.set_disconnected_callback(
                self._make_disconnected_callback(callback),
                **kwargs,
            )

    def _make_disconnected_callback(
        self, callback: Callable[[BleakClient], None] | None
    ) -> Callable[[], None] | None:
        """Make the disconnected callback.

        https://github.com/hbldh/bleak/pull/1256
        The disconnected callback needs to get the top level
        BleakClientWrapper instance, not the backend instance.

        The signature of the callback for the backend is:
            Callable[[], None]

        To make this work we need to wrap the callback in a partial
        that passes the BleakClientWrapper instance as the first
        argument.
        """
        return None if callback is None else partial(callback, self)

    async def connect(self, **kwargs: Any) -> bool:
        """Connect to the specified GATT server."""
        assert models.MANAGER is not None
        manager = models.MANAGER
        if debug_logging := _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("%s: Looking for backend to connect", self.__address)
        wrapped_backend = self._async_get_best_available_backend_and_device(manager)
        device = wrapped_backend.device
        scanner = wrapped_backend.scanner
        self._backend = wrapped_backend.client(
            device,
            disconnected_callback=self._make_disconnected_callback(
                self.__disconnected_callback
            ),
            timeout=self.__timeout,
            hass=manager.hass,
        )
        if debug_logging:
            # Only lookup the description if we are going to log it
            description = ble_device_description(device)
            _, adv = scanner.discovered_devices_and_advertisement_data[device.address]
            rssi = adv.rssi
            _LOGGER.debug(
                "%s: Connecting via %s (last rssi: %s)", description, scanner.name, rssi
            )
        connected = None
        try:
            connected = await super().connect(**kwargs)
        finally:
            # If we failed to connect and its a local adapter (no source)
            # we release the connection slot
            if not connected:
                self.__connect_failures[scanner] = (
                    self.__connect_failures.get(scanner, 0) + 1
                )
                if not wrapped_backend.source:
                    manager.async_release_connection_slot(device)

        if debug_logging:
            _LOGGER.debug(
                "%s: Connected via %s (last rssi: %s)", description, scanner.name, rssi
            )
        return connected

    @hass_callback
    def _async_get_backend_for_ble_device(
        self, manager: BluetoothManager, scanner: BaseHaScanner, ble_device: BLEDevice
    ) -> _HaWrappedBleakBackend | None:
        """Get the backend for a BLEDevice."""
        if not (source := device_source(ble_device)):
            # If client is not defined in details
            # its the client for this platform
            if not manager.async_allocate_connection_slot(ble_device):
                return None
            cls = get_platform_client_backend_type()
            return _HaWrappedBleakBackend(ble_device, scanner, cls, source)

        # Make sure the backend can connect to the device
        # as some backends have connection limits
        if not scanner.connector or not scanner.connector.can_connect():
            return None

        return _HaWrappedBleakBackend(
            ble_device, scanner, scanner.connector.client, source
        )

    @hass_callback
    def _async_get_best_available_backend_and_device(
        self, manager: BluetoothManager
    ) -> _HaWrappedBleakBackend:
        """Get a best available backend and device for the given address.

        This method will return the backend with the best rssi
        that has a free connection slot.
        """
        address = self.__address
        devices = manager.async_scanner_devices_by_address(self.__address, True)
        sorted_devices = sorted(
            devices,
            key=lambda device: device.advertisement.rssi or NO_RSSI_VALUE,
            reverse=True,
        )

        # If we have connection failures we adjust the rssi sorting
        # to prefer the adapter/scanner with the less failures so
        # we don't keep trying to connect with an adapter
        # that is failing
        if self.__connect_failures and len(sorted_devices) > 1:
            # We use the rssi diff between to the top two
            # to adjust the rssi sorter so that each failure
            # will reduce the rssi sorter by the diff amount
            rssi_diff = (
                sorted_devices[0].advertisement.rssi
                - sorted_devices[1].advertisement.rssi
            )
            adjusted_rssi_sorter = partial(
                _rssi_sorter_with_connection_failure_penalty,
                connection_failure_count=self.__connect_failures,
                rssi_diff=rssi_diff,
            )
            sorted_devices = sorted(
                devices,
                key=adjusted_rssi_sorter,
                reverse=True,
            )

        for device in sorted_devices:
            if backend := self._async_get_backend_for_ble_device(
                manager, device.scanner, device.ble_device
            ):
                return backend

        raise BleakError(
            "No backend with an available connection slot that can reach address"
            f" {address} was found"
        )

    async def disconnect(self) -> bool:
        """Disconnect from the device."""
        if self._backend is None:
            return True
        return await self._backend.disconnect()
