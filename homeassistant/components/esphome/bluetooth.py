"""Bluetooth scanner for esphome"""

from dataclasses import dataclass
from datetime import timedelta
import re
import time
import datetime
from aioesphomeapi import APIClient, APIModelBase, converter_field
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import (
    BluetoothManagerCallback,
    ScannerType,
    async_get_advertisement_callback,
    async_register_scanner,
)
from homeassistant.components.bluetooth.models import BaseHaScanner
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

ADV_STALE_TIME = 180  # seconds

TWO = re.compile("..")


@dataclass(frozen=True)
class BluetoothServiceData(APIModelBase):
    uuid: str = ""
    data: list[int] = converter_field(default_factory=list, converter=list)


@dataclass(frozen=True)
class BluetoothLEAdvertisement(APIModelBase):
    address: int = 0
    name: str = ""
    rssi: int = 0

    service_uuids: list[str] = converter_field(default_factory=list, converter=list)
    service_data: list[BluetoothServiceData] = converter_field(
        default_factory=list, converter=list
    )
    manufacturer_data: list[BluetoothServiceData] = converter_field(
        default_factory=list, converter=list
    )


@callback
def long_uuid(uuid: str) -> str:
    """Convert a UUID to a long UUID."""
    return f"0000{uuid[2:].lower()}-1000-8000-00805f9b34fb" if len(uuid) < 8 else uuid


async def async_connect_scanner(
    hass: HomeAssistant, entry: ConfigEntry, cli: APIClient
) -> None:
    """Connect scanner."""
    assert entry.unique_id is not None
    scanner = ESPHomeScannner(
        hass, entry.unique_id, async_get_advertisement_callback(hass)
    )
    entry.async_on_unload(
        async_register_scanner(hass, scanner, ScannerType.NON_CONNECTABLE)
    )
    entry.async_on_unload(scanner.async_setup())
    # await cli.subscribe_bluetooth_le_advertisements(scanner.async_on_advertisement)


class ESPHomeScannner(BaseHaScanner):
    """Scanner for esphome"""

    def __init__(
        self,
        hass: HomeAssistant,
        scanner_id: str,
        manager_callback: BluetoothManagerCallback,
    ) -> None:
        """Initialize the scanner."""
        self._hass = hass
        self._manager_callback = manager_callback
        self._discovered_devices: dict[str, BLEDevice] = {}
        self._discovered_device_timestamps: dict[str, float] = {}
        self._source = scanner_id

    @callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        return async_track_time_interval(
            self._hass, self._async_expire_devices, timedelta(seconds=30)
        )

    def _async_expire_devices(self, dt: datetime.datetime) -> None:
        """Expire old devices."""
        now = time.monotonic()
        expired = [
            address
            for address, timestamp in self._discovered_device_timestamps.items()
            if now - timestamp > ADV_STALE_TIME
        ]
        for address in expired:
            del self._discovered_devices[address]
            del self._discovered_device_timestamps[address]

    @property
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""
        return list(self._discovered_devices.values())

    @callback
    def async_on_advertisement(self, adv: BluetoothLEAdvertisement) -> None:
        """Call the registered callback."""
        now = time.monotonic()
        address = ":".join(TWO.findall("%012X" % adv.address))  # must be upper
        device = BLEDevice(  # type: ignore[no-untyped-call]
            address=address,
            name=adv.name,
            rssi=adv.rssi,
        )
        self._discovered_devices[address] = device
        self._discovered_device_timestamps[address] = now
        adv_data = AdvertisementData(  # type: ignore[no-untyped-call]
            local_name=adv.name,
            manufacturer_data={hex(k): v for k, v in adv.manufacturer_data},
            service_data={long_uuid(k): v for k, v in adv.service_data},
            service_uuids=[long_uuid(hex) for hex in adv.service_uuids],
        )
        self._manager_callback(device, adv_data, now, self._source)
