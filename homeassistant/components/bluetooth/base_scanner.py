"""Base classes for HA Bluetooth scanners for bluetooth."""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Callable, Generator
from contextlib import contextmanager
import datetime
from datetime import timedelta
from typing import Any, Final

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak_retry_connector import NO_RSSI_VALUE
from bluetooth_adapters import adapter_human_name
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import monotonic_time_coarse

from .const import (
    CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from .models import HaBluetoothConnector

REMOTE_SCANNER_STORAGE_VERSION = 1
MONOTONIC_TIME: Final = monotonic_time_coarse


class BaseHaScanner(ABC):
    """Base class for Ha Scanners."""

    __slots__ = ("hass", "source", "_connecting", "name", "scanning")

    def __init__(self, hass: HomeAssistant, source: str, adapter: str) -> None:
        """Initialize the scanner."""
        self.hass = hass
        self.source = source
        self._connecting = 0
        self.name = adapter_human_name(adapter, source) if adapter != source else source
        self.scanning = True

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
        return {
            "type": self.__class__.__name__,
            "discovered_devices_and_advertisement_data": [
                {
                    "name": device_adv[0].name,
                    "address": device_adv[0].address,
                    "rssi": device_adv[0].rssi,
                    "advertisement_data": device_adv[1],
                    "details": device_adv[0].details,
                }
                for device_adv in self.discovered_devices_and_advertisement_data.values()
            ],
        }


def serialize_discovered_device_advertisement_datas(
    discovered_device_advertisement_datas: dict[
        str, tuple[BLEDevice, AdvertisementData]
    ]
) -> dict[str, dict[str, Any]]:
    """Serialize discovered_device_advertisement_datas."""
    data: dict[str, dict[str, Any]] = {}
    for (
        address,
        device_advertisement_data,
    ) in discovered_device_advertisement_datas.items():
        device, advertisement_data = device_advertisement_data
        data[address] = {
            "device": {
                "address": device.address,
                "name": device.name,
                "rssi": device.rssi,
                "details": device.details,
            },
            "advertisement_data": advertisement_data._asdict(),
        }
    return data


def deserialize_discovered_device_advertisement_datas(
    discovered_device_advertisement_datas: dict[str, list[dict[str, Any]]]
) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
    """Deserialize discovered_device_advertisement_datas."""
    data: dict[str, tuple[BLEDevice, AdvertisementData]] = {}
    for (
        address,
        device_advertisement_data,
    ) in discovered_device_advertisement_datas.items():
        device, advertisement_data = device_advertisement_data
        data[address] = (
            BLEDevice(  # type: ignore[no-untyped-call]
                address=device["address"],
                name=device["name"],
                rssi=device["rssi"],
                details=device["details"],
            ),
            AdvertisementData(**advertisement_data),
        )
    return data


class BaseHaRemoteScanner(BaseHaScanner):
    """Base class for a Home Assistant remote BLE scanner."""

    __slots__ = (
        "_new_info_callback",
        "_discovered_device_advertisement_datas",
        "_discovered_device_timestamps",
        "_connector",
        "_connectable",
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
        connector: HaBluetoothConnector,
        connectable: bool,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(hass, scanner_id, name)
        self._new_info_callback = new_info_callback
        self._discovered_device_advertisement_datas: dict[
            str, tuple[BLEDevice, AdvertisementData]
        ] = {}
        self._discovered_device_timestamps: dict[str, float] = {}
        self._connector = connector
        self._connectable = connectable
        self._details: dict[str, str | HaBluetoothConnector] = {"source": scanner_id}
        self._expire_seconds = FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
        self._storage: Store = Store(
            hass,
            REMOTE_SCANNER_STORAGE_VERSION,
            f"bluetooth.remote_scanner.{scanner_id}",
        )
        if connectable:
            self._details["connector"] = connector
            self._expire_seconds = (
                CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
            )

    async def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        if raw_storage := await self._storage.async_load():
            self._discovered_device_advertisement_datas = (
                deserialize_discovered_device_advertisement_datas(
                    raw_storage["discovered_device_advertisement_datas"]
                )
            )
            self._discovered_device_timestamps = raw_storage[
                "discovered_device_timestamps"
            ]

        cancel_track = async_track_time_interval(
            self.hass, self._async_expire_devices, timedelta(seconds=30)
        )
        cancel_save_on_stop = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.async_save
        )

        @hass_callback
        def _cancel() -> None:
            asyncio.create_task(self.async_save())
            cancel_track()
            cancel_save_on_stop()

        return _cancel

    async def async_save(self, event: Event | None = None) -> None:
        """Save the scanner."""
        await self._storage.async_save(self._async_data_to_save())

    def _async_data_to_save(self) -> dict[str, Any]:
        """Return data to save."""
        return {
            "discovered_device_advertisement_datas": serialize_discovered_device_advertisement_datas(
                self._discovered_device_advertisement_datas
            ),
            "discovered_device_timestamps": self._discovered_device_timestamps,
        }

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
        details: dict[Any, Any],
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
                connectable=self._connectable,
                time=now,
            )
        )

    async def async_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the scanner."""
        return await super().async_diagnostics() | {
            "type": self.__class__.__name__,
            "discovered_devices_and_advertisement_data": [
                {
                    "name": device_adv[0].name,
                    "address": device_adv[0].address,
                    "rssi": device_adv[0].rssi,
                    "advertisement_data": device_adv[1],
                    "details": device_adv[0].details,
                }
                for device_adv in self.discovered_devices_and_advertisement_data.values()
            ],
        }
