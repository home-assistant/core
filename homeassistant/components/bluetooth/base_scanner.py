"""Base classes for HA Bluetooth scanners for bluetooth."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
import datetime
from datetime import timedelta
import logging
from typing import Any, Final

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak_retry_connector import NO_RSSI_VALUE
from bluetooth_adapters import DiscoveredDeviceAdvertisementData, adapter_human_name
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util
from homeassistant.util.dt import monotonic_time_coarse

from . import models
from .const import (
    CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    SCANNER_WATCHDOG_INTERVAL,
    SCANNER_WATCHDOG_TIMEOUT,
)
from .models import HaBluetoothConnector

MONOTONIC_TIME: Final = monotonic_time_coarse
_LOGGER = logging.getLogger(__name__)


@dataclass
class BluetoothScannerDevice:
    """Data for a bluetooth device from a given scanner."""

    scanner: BaseHaScanner
    ble_device: BLEDevice
    advertisement: AdvertisementData


class BaseHaScanner(ABC):
    """Base class for Ha Scanners."""

    __slots__ = (
        "hass",
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
    )

    def __init__(
        self,
        hass: HomeAssistant,
        source: str,
        adapter: str,
        connector: HaBluetoothConnector | None = None,
    ) -> None:
        """Initialize the scanner."""
        self.hass = hass
        self.connectable = False
        self.source = source
        self.connector = connector
        self._connecting = 0
        self.adapter = adapter
        self.name = adapter_human_name(adapter, source) if adapter != source else source
        self.scanning = True
        self._last_detection = 0.0
        self._start_time = 0.0
        self._cancel_watchdog: CALLBACK_TYPE | None = None

    @hass_callback
    def _async_stop_scanner_watchdog(self) -> None:
        """Stop the scanner watchdog."""
        if self._cancel_watchdog:
            self._cancel_watchdog()
            self._cancel_watchdog = None

    @hass_callback
    def _async_setup_scanner_watchdog(self) -> None:
        """If something has restarted or updated, we need to restart the scanner."""
        self._start_time = self._last_detection = MONOTONIC_TIME()
        if not self._cancel_watchdog:
            self._cancel_watchdog = async_track_time_interval(
                self.hass, self._async_scanner_watchdog, SCANNER_WATCHDOG_INTERVAL
            )

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
    def _async_scanner_watchdog(self, now: datetime.datetime) -> None:
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
                    "name": device_adv[0].name,
                    "address": device_adv[0].address,
                    "rssi": device_adv[0].rssi,
                    "advertisement_data": device_adv[1],
                    "details": device_adv[0].details,
                }
                for device_adv in device_adv_datas
            ],
        }


class BaseHaRemoteScanner(BaseHaScanner):
    """Base class for a Home Assistant remote BLE scanner."""

    __slots__ = (
        "_new_info_callback",
        "_discovered_device_advertisement_datas",
        "_discovered_device_timestamps",
        "_details",
        "_expire_seconds",
        "_storage",
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
        super().__init__(hass, scanner_id, name, connector)
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
        assert models.MANAGER is not None
        self._storage = models.MANAGER.storage

    @hass_callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        if history := self._storage.async_get_advertisement_history(self.source):
            self._discovered_device_advertisement_datas = (
                history.discovered_device_advertisement_datas
            )
            self._discovered_device_timestamps = history.discovered_device_timestamps
            # Expire anything that is too old
            self._async_expire_devices(dt_util.utcnow())

        cancel_track = async_track_time_interval(
            self.hass, self._async_expire_devices, timedelta(seconds=30)
        )
        cancel_stop = self.hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, self._save_history
        )
        self._async_setup_scanner_watchdog()

        @hass_callback
        def _cancel() -> None:
            self._save_history()
            self._async_stop_scanner_watchdog()
            cancel_track()
            cancel_stop()

        return _cancel

    def _save_history(self, event: Event | None = None) -> None:
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
    ) -> None:
        """Call the registered callback."""
        now = MONOTONIC_TIME()
        self._last_detection = now
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
            if service_uuids and service_uuids != prev_advertisement.service_uuids:
                service_uuids = list(
                    set(service_uuids + prev_advertisement.service_uuids)
                )
            elif not service_uuids:
                service_uuids = prev_advertisement.service_uuids
            if service_data and service_data != prev_advertisement.service_data:
                service_data = {**prev_advertisement.service_data, **service_data}
            elif not service_data:
                service_data = prev_advertisement.service_data
            if (
                manufacturer_data
                and manufacturer_data != prev_advertisement.manufacturer_data
            ):
                manufacturer_data = {
                    **prev_advertisement.manufacturer_data,
                    **manufacturer_data,
                }
            elif not manufacturer_data:
                manufacturer_data = prev_advertisement.manufacturer_data

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
            details=self._details | details,
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
                connectable=self.connectable,
                time=now,
            )
        )

    async def async_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the scanner."""
        now = MONOTONIC_TIME()
        return await super().async_diagnostics() | {
            "storage": self._storage.async_get_advertisement_history_as_dict(
                self.source
            ),
            "connectable": self.connectable,
            "discovered_device_timestamps": self._discovered_device_timestamps,
            "time_since_last_device_detection": {
                address: now - timestamp
                for address, timestamp in self._discovered_device_timestamps.items()
            },
        }
