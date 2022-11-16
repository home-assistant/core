"""Models for bluetooth."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable
import contextlib
from dataclasses import dataclass
import datetime
from datetime import timedelta
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
from bleak_retry_connector import NO_RSSI_VALUE, freshen_ble_device
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.frame import report
from homeassistant.helpers.service_info.bluetooth import (  # noqa: F401 # pylint: disable=unused-import
    BluetoothServiceInfo,
)
from homeassistant.util.dt import monotonic_time_coarse

from .const import FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS

# The maximum time between advertisements for a device to be considered
# stale when the advertisement tracker can determine the interval for
# connectable devices.
#
# BlueZ uses 180 seconds by default but we give it a bit more time
# to account for the esp32's bluetooth stack being a bit slower
# than BlueZ's.
CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS: Final = 195

if TYPE_CHECKING:

    from .manager import BluetoothManager


_LOGGER = logging.getLogger(__name__)

FILTER_UUIDS: Final = "UUIDs"

MANAGER: BluetoothManager | None = None

MONOTONIC_TIME: Final = monotonic_time_coarse


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


@dataclass
class _HaWrappedBleakBackend:
    """Wrap bleak backend to make it usable by Home Assistant."""

    device: BLEDevice
    client: type[BaseBleakClient]


class BaseHaScanner:
    """Base class for Ha Scanners."""

    def __init__(self, hass: HomeAssistant, source: str) -> None:
        """Initialize the scanner."""
        self.hass = hass
        self.source = source

    @property
    @abstractmethod
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""

    @property
    @abstractmethod
    def discovered_devices_and_advertisement_data(
        self,
    ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
        """Return a list of discovered devices and their advertisement data."""

    async def async_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the scanner."""
        return {
            "type": self.__class__.__name__,
            "discovered_devices": [
                {
                    "name": device.name,
                    "address": device.address,
                }
                for device in self.discovered_devices
            ],
        }


class BaseHaRemoteScanner(BaseHaScanner):
    """Base class for a Home Assistant remote BLE scanner."""

    def __init__(
        self,
        hass: HomeAssistant,
        scanner_id: str,
        new_info_callback: Callable[[BluetoothServiceInfoBleak], None],
        connector: HaBluetoothConnector,
        connectable: bool,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(hass, scanner_id)
        self._new_info_callback = new_info_callback
        self._discovered_device_advertisement_datas: dict[
            str, tuple[BLEDevice, AdvertisementData]
        ] = {}
        self._discovered_device_timestamps: dict[str, float] = {}
        self._connector = connector
        self._connectable = connectable
        self._details: dict[str, str | HaBluetoothConnector] = {"source": scanner_id}
        self._expire_seconds = FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
        if connectable:
            self._details["connector"] = connector
            self._expire_seconds = (
                CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
            )

    @hass_callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        return async_track_time_interval(
            self.hass, self._async_expire_devices, timedelta(seconds=30)
        )

    def _async_expire_devices(self, _datetime: datetime.datetime) -> None:
        """Expire old devices."""
        now = MONOTONIC_TIME()
        expired = [
            address
            for address, timestamp in self._discovered_device_timestamps.items()
            if now - timestamp > self._expire_seconds
        ]
        for address in expired:
            del self._discovered_device_advertisement_datas[address]
            del self._discovered_device_timestamps[address]

    @property
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""
        return [
            device_advertisement_data[0]
            for device_advertisement_data in self._discovered_device_advertisement_datas.values()
        ]

    @property
    def discovered_devices_and_advertisement_data(
        self,
    ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
        """Return a list of discovered devices and advertisement data."""
        return self._discovered_device_advertisement_datas

    @hass_callback
    def _async_on_advertisement(
        self,
        address: str,
        rssi: int,
        local_name: str | None,
        service_uuids: list[str],
        service_data: dict[str, bytes],
        manufacturer_data: dict[int, bytes],
        tx_power: int | None,
    ) -> None:
        """Call the registered callback."""
        now = MONOTONIC_TIME()
        if prev_discovery := self._discovered_device_advertisement_datas.get(address):
            # Merge the new data with the old data
            # to function the same as BlueZ which
            # merges the dicts on PropertiesChanged
            prev_device = prev_discovery[0]
            prev_advertisement = prev_discovery[1]
            if (
                local_name
                and prev_device.name
                and len(prev_device.name) > len(local_name)
            ):
                local_name = prev_device.name
            if prev_advertisement.service_uuids:
                service_uuids = list(
                    set(service_uuids + prev_advertisement.service_uuids)
                )
            if prev_advertisement.service_data:
                service_data = {**prev_advertisement.service_data, **service_data}
            if prev_advertisement.manufacturer_data:
                manufacturer_data = {
                    **prev_advertisement.manufacturer_data,
                    **manufacturer_data,
                }

        advertisement_data = AdvertisementData(
            local_name=None if local_name == "" else local_name,
            manufacturer_data=manufacturer_data,
            service_data=service_data,
            service_uuids=service_uuids,
            rssi=rssi,
            tx_power=NO_RSSI_VALUE if tx_power is None else tx_power,
            platform_data=(),
        )
        device = BLEDevice(  # type: ignore[no-untyped-call]
            address=address,
            name=local_name,
            details=self._details,
            rssi=rssi,  # deprecated, will be removed in newer bleak
        )
        self._discovered_device_advertisement_datas[address] = (
            device,
            advertisement_data,
        )
        self._discovered_device_timestamps[address] = now
        self._new_info_callback(
            BluetoothServiceInfoBleak(
                name=advertisement_data.local_name or device.name or device.address,
                address=device.address,
                rssi=rssi,
                manufacturer_data=advertisement_data.manufacturer_data,
                service_data=advertisement_data.service_data,
                service_uuids=advertisement_data.service_uuids,
                source=self.source,
                device=device,
                advertisement=advertisement_data,
                connectable=self._connectable,
                time=now,
            )
        )


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

    @classmethod
    async def discover(cls, timeout: float = 5.0, **kwargs: Any) -> list[BLEDevice]:
        """Discover devices."""
        assert MANAGER is not None
        return list(MANAGER.async_discovered_devices(True))

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
        self.__ble_device: BLEDevice | None = None
        self._backend: BaseBleakClient | None = None  # type: ignore[assignment]

    @property
    def is_connected(self) -> bool:
        """Return True if the client is connected to a device."""
        return self._backend is not None and self._backend.is_connected

    def set_disconnected_callback(
        self,
        callback: Callable[[BleakClient], None] | None,
        **kwargs: Any,
    ) -> None:
        """Set the disconnect callback."""
        self.__disconnected_callback = callback
        if self._backend:
            self._backend.set_disconnected_callback(callback, **kwargs)  # type: ignore[arg-type]

    async def connect(self, **kwargs: Any) -> bool:
        """Connect to the specified GATT server."""
        if (
            not self._backend
            or not self.__ble_device
            or not self._async_get_backend_for_ble_device(self.__ble_device)
        ):
            assert MANAGER is not None
            wrapped_backend = (
                self._async_get_backend() or self._async_get_fallback_backend()
            )
            self.__ble_device = (
                await freshen_ble_device(wrapped_backend.device)
                or wrapped_backend.device
            )
            self._backend = wrapped_backend.client(
                self.__ble_device,
                disconnected_callback=self.__disconnected_callback,
                timeout=self.__timeout,
                hass=MANAGER.hass,
            )
        return await super().connect(**kwargs)

    @hass_callback
    def _async_get_backend_for_ble_device(
        self, ble_device: BLEDevice
    ) -> _HaWrappedBleakBackend | None:
        """Get the backend for a BLEDevice."""
        details = ble_device.details
        if not isinstance(details, dict) or "connector" not in details:
            # If client is not defined in details
            # its the client for this platform
            cls = get_platform_client_backend_type()
            return _HaWrappedBleakBackend(ble_device, cls)

        connector: HaBluetoothConnector = details["connector"]
        # Make sure the backend can connect to the device
        # as some backends have connection limits
        if not connector.can_connect():
            return None

        return _HaWrappedBleakBackend(ble_device, connector.client)

    @hass_callback
    def _async_get_backend(self) -> _HaWrappedBleakBackend | None:
        """Get the bleak backend for the given address."""
        assert MANAGER is not None
        address = self.__address
        ble_device = MANAGER.async_ble_device_from_address(address, True)
        if ble_device is None:
            raise BleakError(f"No device found for address {address}")

        if backend := self._async_get_backend_for_ble_device(ble_device):
            return backend

        return None

    @hass_callback
    def _async_get_fallback_backend(self) -> _HaWrappedBleakBackend:
        """Get a fallback backend for the given address."""
        #
        # The preferred backend cannot currently connect the device
        # because it is likely out of connection slots.
        #
        # We need to try all backends to find one that can
        # connect to the device.
        #
        assert MANAGER is not None
        address = self.__address
        device_advertisement_datas = (
            MANAGER.async_get_discovered_devices_and_advertisement_data_by_address(
                address, True
            )
        )
        for device_advertisement_data in sorted(
            device_advertisement_datas,
            key=lambda device_advertisement_data: device_advertisement_data[1].rssi
            or NO_RSSI_VALUE,
            reverse=True,
        ):
            if backend := self._async_get_backend_for_ble_device(
                device_advertisement_data[0]
            ):
                return backend

        raise BleakError(
            f"No backend with an available connection slot that can reach address {address} was found"
        )

    async def disconnect(self) -> bool:
        """Disconnect from the device."""
        if self._backend is None:
            return True
        return await self._backend.disconnect()
