"""Storage for remote scanners."""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Final, TypedDict

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import monotonic_time_coarse

REMOTE_SCANNER_STORAGE_VERSION = 1
SCANNER_SAVE_DELAY = 10
MONOTONIC_TIME: Final = monotonic_time_coarse


@dataclass
class DiscoveredDeviceAdvertisementData:
    """Discovered device advertisement data deserialized from storage."""

    connectable: bool
    expire_seconds: float
    discovered_device_advertisement_datas: dict[
        str, tuple[BLEDevice, AdvertisementData]
    ]
    discovered_device_timestamps: dict[str, float]


class DiscoveredDeviceAdvertisementDataDict(TypedDict):
    """Discovered device advertisement data dict in storage."""

    connectable: bool
    expire_seconds: float
    discovered_device_advertisement_datas: dict[str, dict[str, dict[str, Any]]]
    discovered_device_timestamps: dict[str, float]


class BluetoothStorage:
    """Storage for remote scanners."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the storage."""
        self._store: Store[dict[str, DiscoveredDeviceAdvertisementDataDict]] = Store(
            hass, REMOTE_SCANNER_STORAGE_VERSION, "bluetooth.remote_scanners"
        )
        self._data: dict[str, DiscoveredDeviceAdvertisementDataDict] = {}

    async def async_setup(self) -> None:
        """Set up the storage."""
        self._data = await self._store.async_load() or {}
        now = time.time()
        expired_scanners: list[str] = []
        for scanner, data in self._data.items():
            expire: list[str] = []
            expire_seconds = data["expire_seconds"]
            timestamps = data["discovered_device_timestamps"]
            discovered_device_advertisement_datas = data[
                "discovered_device_advertisement_datas"
            ]
            for address, timestamp in timestamps.items():
                if now - timestamp > expire_seconds:
                    expire.append(address)
            for address in expire:
                del timestamps[address]
                del discovered_device_advertisement_datas[address]
            if not timestamps:
                expired_scanners.append(scanner)
        for scanner in expired_scanners:
            del self._data[scanner]

    def scanners(self) -> list[str]:
        """Get all scanners."""
        return list(self._data.keys())

    @callback
    def async_get_advertisement_history(
        self, scanner: str
    ) -> DiscoveredDeviceAdvertisementData | None:
        """Get discovered devices by scanner."""
        if not (scanner_data := self._data.get(scanner)):
            return None
        return DiscoveredDeviceAdvertisementData(
            scanner_data["connectable"],
            scanner_data["expire_seconds"],
            deserialize_discovered_device_advertisement_datas(
                scanner_data["discovered_device_advertisement_datas"]
            ),
            deserialize_discovered_device_timestamps(
                scanner_data["discovered_device_timestamps"]
            ),
        )

    @callback
    def _async_get_data(self) -> dict[str, DiscoveredDeviceAdvertisementDataDict]:
        """Get data to save to disk."""
        return self._data

    @callback
    def async_set_advertisement_history(
        self,
        scanner: str,
        connectable: bool,
        expire_seconds: float,
        discovered_device_advertisement_datas: dict[
            str, tuple[BLEDevice, AdvertisementData]
        ],
        discovered_device_timestamps: dict[str, float],
    ) -> None:
        """Set discovered devices by scanner."""
        self._data[scanner] = DiscoveredDeviceAdvertisementDataDict(
            connectable=connectable,
            expire_seconds=expire_seconds,
            discovered_device_advertisement_datas=serialize_discovered_device_advertisement_datas(
                discovered_device_advertisement_datas
            ),
            discovered_device_timestamps=serialize_discovered_device_timestamps(
                discovered_device_timestamps
            ),
        )
        self._store.async_delay_save(self._async_get_data, SCANNER_SAVE_DELAY)


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
            "advertisement_data": {
                "local_name": advertisement_data.local_name,
                "manufacturer_data": {
                    manufacturer_id: manufacturer_data.hex()
                    for manufacturer_id, manufacturer_data in advertisement_data.manufacturer_data.items()
                },
                "service_data": {
                    service_uuid: service_data.hex()
                    for service_uuid, service_data in advertisement_data.service_data.items()
                },
                "service_uuids": advertisement_data.service_uuids,
                "tx_power": advertisement_data.tx_power,
                "rssi": advertisement_data.rssi,
            },
        }
    return data


def deserialize_discovered_device_advertisement_datas(
    discovered_device_advertisement_datas: dict[str, dict[str, dict[str, Any]]]
) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
    """Deserialize discovered_device_advertisement_datas."""
    data: dict[str, tuple[BLEDevice, AdvertisementData]] = {}
    for (
        address,
        device_advertisement_data,
    ) in discovered_device_advertisement_datas.items():
        device = device_advertisement_data["device"]
        advertisement_data = device_advertisement_data["advertisement_data"]
        data[address] = (
            BLEDevice(  # type: ignore[no-untyped-call]
                address=device["address"],
                name=device["name"],
                rssi=device["rssi"],
                details=device["details"],
            ),
            AdvertisementData(
                local_name=advertisement_data["local_name"],
                manufacturer_data={
                    manufacturer_id: bytes.fromhex(manufacturer_data)
                    for manufacturer_id, manufacturer_data in advertisement_data[
                        "manufacturer_data"
                    ].items()
                },
                service_data={
                    service_uuid: bytes.fromhex(service_data)
                    for service_uuid, service_data in advertisement_data[
                        "service_data"
                    ].items()
                },
                service_uuids=advertisement_data["service_uuids"],
                rssi=advertisement_data["rssi"],
                tx_power=advertisement_data["tx_power"],
                platform_data=(),
            ),
        )
    return data


def deserialize_discovered_device_timestamps(
    discovered_device_timestamps: dict[str, float]
) -> dict[str, float]:
    """Deserialize discovered_device_timestamps."""
    time_diff = time.time() - MONOTONIC_TIME()
    return {
        address: unix_time - time_diff
        for address, unix_time in discovered_device_timestamps.items()
    }


def serialize_discovered_device_timestamps(
    discovered_device_timestamps: dict[str, float]
) -> dict[str, float]:
    """Serialize discovered_device_timestamps."""
    time_diff = time.time() - MONOTONIC_TIME()
    return {
        address: monotonic_time + time_diff
        for address, monotonic_time in discovered_device_timestamps.items()
    }
