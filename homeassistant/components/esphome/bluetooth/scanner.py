"""Bluetooth scanner for esphome."""
from __future__ import annotations

from collections.abc import Callable
import datetime
from datetime import timedelta
import re
import time

from aioesphomeapi import BluetoothLEAdvertisement
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BaseHaScanner, HaBluetoothConnector
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

# We have to set this quite high as we don't know
# when devices fall out of the esphome device's stack
# like we do with BlueZ so its safer to assume its available
# since if it does go out of range and it is in range
# of another device the timeout is much shorter and it will
# switch over to using that adapter anyways.
ADV_STALE_TIME = 60 * 15  # seconds

TWO_CHAR = re.compile("..")


class ESPHomeScanner(BaseHaScanner):
    """Scanner for esphome."""

    def __init__(
        self,
        hass: HomeAssistant,
        scanner_id: str,
        new_info_callback: Callable[[BluetoothServiceInfoBleak], None],
        connector: HaBluetoothConnector,
        connectable: bool,
    ) -> None:
        """Initialize the scanner."""
        self._hass = hass
        self._new_info_callback = new_info_callback
        self._discovered_devices: dict[str, BLEDevice] = {}
        self._discovered_device_timestamps: dict[str, float] = {}
        self._source = scanner_id
        self._connector = connector
        self._connectable = connectable
        self._details: dict[str, str | HaBluetoothConnector] = {"source": scanner_id}
        if connectable:
            self._details["connector"] = connector

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

    async def async_get_device_by_address(self, address: str) -> BLEDevice | None:
        """Get a device by address."""
        return self._discovered_devices.get(address)

    @callback
    def async_on_advertisement(self, adv: BluetoothLEAdvertisement) -> None:
        """Call the registered callback."""
        now = time.monotonic()
        address = ":".join(TWO_CHAR.findall("%012X" % adv.address))  # must be upper
        name = adv.name
        if prev_discovery := self._discovered_devices.get(address):
            # If the last discovery had the full local name
            # and this one doesn't, keep the old one as we
            # always want the full local name over the short one
            if len(prev_discovery.name) > len(adv.name):
                name = prev_discovery.name

        advertisement_data = AdvertisementData(  # type: ignore[no-untyped-call]
            local_name=None if name == "" else name,
            manufacturer_data=adv.manufacturer_data,
            service_data=adv.service_data,
            service_uuids=adv.service_uuids,
        )
        device = BLEDevice(  # type: ignore[no-untyped-call]
            address=address,
            name=name,
            details=self._details,
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
                connectable=self._connectable,
                time=now,
            )
        )
