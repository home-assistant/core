"""Base classes for HA Bluetooth scanners for bluetooth."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
import logging
from typing import Any, Final, final

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak_retry_connector import NO_RSSI_VALUE
from bluetooth_adapters import DiscoveredDeviceAdvertisementData, adapter_human_name
from bluetooth_data_tools import monotonic_time_coarse
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)

from . import models
from .const import (
    CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    SCANNER_WATCHDOG_INTERVAL,
    SCANNER_WATCHDOG_TIMEOUT,
)
from .models import HaBluetoothConnector

SCANNER_WATCHDOG_INTERVAL_SECONDS: Final = SCANNER_WATCHDOG_INTERVAL.total_seconds()
MONOTONIC_TIME: Final = monotonic_time_coarse
_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class BluetoothScannerDevice:
    """Data for a bluetooth device from a given scanner."""

    scanner: BaseHaScanner
    ble_device: BLEDevice
    advertisement: AdvertisementData


class BaseHaScanner:
    """Base class for high availability BLE scanners."""

    __slots__ = (
        "adapter",
        "connectable",
        "source",
        "connector",
        "_connecting",
        "name",
        "scanning",
        "_last_detection",
        "_start_time",
        "_cancel_watchdog",
        "_loop",
    )

    def __init__(
        self,
        source: str,
        adapter: str,
        connector: HaBluetoothConnector | None = None,
    ) -> None:
        """Initialize the scanner."""
        self.connectable = False
        self.source = source
        self.connector = connector
        self._connecting = 0
        self.adapter = adapter
        self.name = adapter_human_name(adapter, source) if adapter != source else source
        self.scanning = True
        self._last_detection = 0.0
        self._start_time = 0.0
        self._cancel_watchdog: asyncio.TimerHandle | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @hass_callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        self._loop = asyncio.get_running_loop()
        return self._unsetup

    @hass_callback
    def _async_stop_scanner_watchdog(self) -> None:
        """Stop the scanner watchdog."""
        if self._cancel_watchdog:
            self._cancel_watchdog.cancel()
            self._cancel_watchdog = None

    @hass_callback
    def _async_setup_scanner_watchdog(self) -> None:
        """If something has restarted or updated, we need to restart the scanner."""
        self._start_time = self._last_detection = MONOTONIC_TIME()
        if not self._cancel_watchdog:
            self._schedule_watchdog()

    def _schedule_watchdog(self) -> None:
        """Schedule the watchdog."""
        loop = self._loop
        assert loop is not None
        self._cancel_watchdog = loop.call_at(
            loop.time() + SCANNER_WATCHDOG_INTERVAL_SECONDS,
            self._async_call_scanner_watchdog,
        )

    @final
    def _async_call_scanner_watchdog(self) -> None:
        """Call the scanner watchdog and schedule the next one."""
        self._async_scanner_watchdog()
        self._schedule_watchdog()

    @hass_callback
    def _async_watchdog_triggered(self) -> bool:
        """Check if the watchdog has been triggered."""
        time_since_last_detection = MONOTONIC_TIME() - self._last_detection
        _LOGGER.debug(
            "%s: Scanner watchdog time_since_last_detection: %s",
            self.name,
            time_since_last_detection,
        )
        return time_since_last_detection > SCANNER_WATCHDOG_TIMEOUT

    @hass_callback
    def _async_scanner_watchdog(self) -> None:
        """Check if the scanner is running.

        Override this method if you need to do something else when the watchdog
        is triggered.
        """
        if self._async_watchdog_triggered():
            _LOGGER.info(
                (
                    "%s: Bluetooth scanner has gone quiet for %ss, check logs on the"
                    " scanner device for more information"
                ),
                self.name,
                SCANNER_WATCHDOG_TIMEOUT,
            )
            self.scanning = False
            return
        self.scanning = not self._connecting

    @hass_callback
    def _unsetup(self) -> None:
        """Unset up the scanner."""

    @contextmanager
    def connecting(self) -> Generator[None, None, None]:
        """Context manager to track connecting state."""
        self._connecting += 1
        self.scanning = not self._connecting
        try:
            yield
        finally:
            self._connecting -= 1
            self.scanning = not self._connecting

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
        device_adv_datas = self.discovered_devices_and_advertisement_data.values()
        return {
            "name": self.name,
            "start_time": self._start_time,
            "source": self.source,
            "scanning": self.scanning,
            "type": self.__class__.__name__,
            "last_detection": self._last_detection,
            "monotonic_time": MONOTONIC_TIME(),
            "discovered_devices_and_advertisement_data": [
                {
                    "name": device.name,
                    "address": device.address,
                    "rssi": advertisement_data.rssi,
                    "advertisement_data": advertisement_data,
                    "details": device.details,
                }
                for device, advertisement_data in device_adv_datas
            ],
        }


class BaseHaRemoteScanner(BaseHaScanner):
    """Base class for a high availability remote BLE scanner."""

    __slots__ = (
        "_new_info_callback",
        "_discovered_device_advertisement_datas",
        "_discovered_device_timestamps",
        "_details",
        "_expire_seconds",
        "_cancel_track",
    )

    def __init__(
        self,
        scanner_id: str,
        name: str,
        new_info_callback: Callable[[BluetoothServiceInfoBleak], None],
        connector: HaBluetoothConnector | None,
        connectable: bool,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(scanner_id, name, connector)
        self._new_info_callback = new_info_callback
        self._discovered_device_advertisement_datas: dict[
            str, tuple[BLEDevice, AdvertisementData]
        ] = {}
        self._discovered_device_timestamps: dict[str, float] = {}
        self.connectable = connectable
        self._details: dict[str, str | HaBluetoothConnector] = {"source": scanner_id}
        # Scanners only care about connectable devices. The manager
        # will handle taking care of availability for non-connectable devices
        self._expire_seconds = CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
        self._cancel_track: asyncio.TimerHandle | None = None

    def _cancel_expire_devices(self) -> None:
        """Cancel the expiration of old devices."""
        if self._cancel_track:
            self._cancel_track.cancel()
            self._cancel_track = None

    @hass_callback
    def _unsetup(self) -> None:
        """Unset up the scanner."""
        self._async_stop_scanner_watchdog()
        self._cancel_expire_devices()

    @hass_callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        super().async_setup()
        self._schedule_expire_devices()
        self._async_setup_scanner_watchdog()
        return self._unsetup

    def _schedule_expire_devices(self) -> None:
        """Schedule the expiration of old devices."""
        loop = self._loop
        assert loop is not None
        self._cancel_expire_devices()
        self._cancel_track = loop.call_at(loop.time() + 30, self._async_expire_devices)

    @hass_callback
    def _async_expire_devices(self) -> None:
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
        self._schedule_expire_devices()

    @property
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""
        device_adv_datas = self._discovered_device_advertisement_datas.values()
        return [
            device_advertisement_data[0]
            for device_advertisement_data in device_adv_datas
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
        details: dict[Any, Any],
        advertisement_monotonic_time: float,
    ) -> None:
        """Call the registered callback."""
        self.scanning = not self._connecting
        self._last_detection = advertisement_monotonic_time
        try:
            prev_discovery = self._discovered_device_advertisement_datas[address]
        except KeyError:
            # We expect this is the rare case and since py3.11+ has
            # near zero cost try on success, and we can avoid .get()
            # which is slower than [] we use the try/except pattern.
            device = BLEDevice(
                address=address,
                name=local_name,
                details=self._details | details,
                rssi=rssi,  # deprecated, will be removed in newer bleak
            )
        else:
            # Merge the new data with the old data
            # to function the same as BlueZ which
            # merges the dicts on PropertiesChanged
            prev_device = prev_discovery[0]
            prev_advertisement = prev_discovery[1]
            prev_service_uuids = prev_advertisement.service_uuids
            prev_service_data = prev_advertisement.service_data
            prev_manufacturer_data = prev_advertisement.manufacturer_data
            prev_name = prev_device.name

            if prev_name and (not local_name or len(prev_name) > len(local_name)):
                local_name = prev_name

            if service_uuids and service_uuids != prev_service_uuids:
                service_uuids = list({*service_uuids, *prev_service_uuids})
            elif not service_uuids:
                service_uuids = prev_service_uuids

            if service_data and service_data != prev_service_data:
                service_data = prev_service_data | service_data
            elif not service_data:
                service_data = prev_service_data

            if manufacturer_data and manufacturer_data != prev_manufacturer_data:
                manufacturer_data = prev_manufacturer_data | manufacturer_data
            elif not manufacturer_data:
                manufacturer_data = prev_manufacturer_data
            #
            # Bleak updates the BLEDevice via create_or_update_device.
            # We need to do the same to ensure integrations that already
            # have the BLEDevice object get the updated details when they
            # change.
            #
            # https://github.com/hbldh/bleak/blob/222618b7747f0467dbb32bd3679f8cfaa19b1668/bleak/backends/scanner.py#L203
            #
            device = prev_device
            device.name = local_name
            device.details = self._details | details
            # pylint: disable-next=protected-access
            device._rssi = rssi  # deprecated, will be removed in newer bleak

        advertisement_data = AdvertisementData(
            local_name=None if local_name == "" else local_name,
            manufacturer_data=manufacturer_data,
            service_data=service_data,
            service_uuids=service_uuids,
            tx_power=NO_RSSI_VALUE if tx_power is None else tx_power,
            rssi=rssi,
            platform_data=(),
        )
        self._discovered_device_advertisement_datas[address] = (
            device,
            advertisement_data,
        )
        self._discovered_device_timestamps[address] = advertisement_monotonic_time
        self._new_info_callback(
            BluetoothServiceInfoBleak(
                name=local_name or address,
                address=address,
                rssi=rssi,
                manufacturer_data=manufacturer_data,
                service_data=service_data,
                service_uuids=service_uuids,
                source=self.source,
                device=device,
                advertisement=advertisement_data,
                connectable=self.connectable,
                time=advertisement_monotonic_time,
            )
        )

    async def async_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the scanner."""
        now = MONOTONIC_TIME()
        return await super().async_diagnostics() | {
            "connectable": self.connectable,
            "discovered_device_timestamps": self._discovered_device_timestamps,
            "time_since_last_device_detection": {
                address: now - timestamp
                for address, timestamp in self._discovered_device_timestamps.items()
            },
        }


class HomeAssistantRemoteScanner(BaseHaRemoteScanner):
    """Home Assistant remote BLE scanner.

    This is the only object that should know about
    the hass object.
    """

    __slots__ = (
        "hass",
        "_storage",
        "_cancel_stop",
    )

    def __init__(
        self,
        hass: HomeAssistant,
        scanner_id: str,
        name: str,
        new_info_callback: Callable[[BluetoothServiceInfoBleak], None],
        connector: HaBluetoothConnector | None,
        connectable: bool,
    ) -> None:
        """Initialize the scanner."""
        self.hass = hass
        assert models.MANAGER is not None
        self._storage = models.MANAGER.storage
        self._cancel_stop: CALLBACK_TYPE | None = None
        super().__init__(scanner_id, name, new_info_callback, connector, connectable)

    @hass_callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        super().async_setup()
        if history := self._storage.async_get_advertisement_history(self.source):
            self._discovered_device_advertisement_datas = (
                history.discovered_device_advertisement_datas
            )
            self._discovered_device_timestamps = history.discovered_device_timestamps
            # Expire anything that is too old
            self._async_expire_devices()

        self._cancel_stop = self.hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, self._async_save_history
        )
        return self._unsetup

    @hass_callback
    def _unsetup(self) -> None:
        super()._unsetup()
        self._async_save_history()
        if self._cancel_stop:
            self._cancel_stop()
            self._cancel_stop = None

    @hass_callback
    def _async_save_history(self, event: Event | None = None) -> None:
        """Save the history."""
        self._storage.async_set_advertisement_history(
            self.source,
            DiscoveredDeviceAdvertisementData(
                self.connectable,
                self._expire_seconds,
                self._discovered_device_advertisement_datas,
                self._discovered_device_timestamps,
            ),
        )

    async def async_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the scanner."""
        diag = await super().async_diagnostics()
        diag["storage"] = self._storage.async_get_advertisement_history_as_dict(
            self.source
        )
        return diag
