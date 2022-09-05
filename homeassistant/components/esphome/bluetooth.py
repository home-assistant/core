"""Bluetooth scanner for esphome."""

from collections.abc import Callable
import datetime
from datetime import timedelta
import re
import time

from aioesphomeapi import APIClient, BluetoothLEAdvertisement
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import (
    BaseHaScanner,
    async_get_advertisement_callback,
    async_register_scanner,
)
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

ADV_STALE_TIME = 180  # seconds

TWO_CHAR = re.compile("..")


async def async_connect_scanner(
    hass: HomeAssistant, entry: ConfigEntry, cli: APIClient
) -> None:
    """Connect scanner."""
    assert entry.unique_id is not None
    new_info_callback = async_get_advertisement_callback(hass)
    scanner = ESPHomeScannner(hass, entry.unique_id, new_info_callback)
    entry.async_on_unload(async_register_scanner(hass, scanner, False))
    entry.async_on_unload(scanner.async_setup())
    await cli.subscribe_bluetooth_le_advertisements(scanner.async_on_advertisement)


class ESPHomeScannner(BaseHaScanner):
    """Scanner for esphome."""

    def __init__(
        self,
        hass: HomeAssistant,
        scanner_id: str,
        new_info_callback: Callable[[BluetoothServiceInfoBleak], None],
    ) -> None:
        """Initialize the scanner."""
        self._hass = hass
        self._new_info_callback = new_info_callback
        self._discovered_devices: dict[str, BLEDevice] = {}
        self._discovered_device_timestamps: dict[str, float] = {}
        self._source = scanner_id

    @callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        return async_track_time_interval(
            self._hass, self._async_expire_devices, timedelta(seconds=30)
        )

    def _async_expire_devices(self, _datetime: datetime.datetime) -> None:
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
        address = ":".join(TWO_CHAR.findall("%012X" % adv.address))  # must be upper
        advertisement_data = AdvertisementData(  # type: ignore[no-untyped-call]
            local_name=None if adv.name == "" else adv.name,
            manufacturer_data=adv.manufacturer_data,
            service_data=adv.service_data,
            service_uuids=adv.service_uuids,
        )
        device = BLEDevice(  # type: ignore[no-untyped-call]
            address=address,
            name=adv.name,
            details={},
            rssi=adv.rssi,
        )
        self._discovered_devices[address] = device
        self._discovered_device_timestamps[address] = now
        self._new_info_callback(
            BluetoothServiceInfoBleak(
                name=advertisement_data.local_name or device.name or device.address,
                address=device.address,
                rssi=device.rssi,
                manufacturer_data=advertisement_data.manufacturer_data,
                service_data=advertisement_data.service_data,
                service_uuids=advertisement_data.service_uuids,
                source=self._source,
                device=device,
                advertisement=advertisement_data,
                connectable=False,
                time=now,
            )
        )
