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

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    BaseHaScanner,
    BluetoothServiceInfoBleak,
    HaBluetoothConnector,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import monotonic_time_coarse

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
        super().__init__(hass, scanner_id)
        self._new_info_callback = new_info_callback
        self._discovered_device_advertisement_datas: dict[
            str, tuple[BLEDevice, AdvertisementData]
        ] = {}
        self._discovered_device_timestamps: dict[str, float] = {}
        self._connector = connector
        self._connectable = connectable
        self._details: dict[str, str | HaBluetoothConnector] = {"source": scanner_id}
        if connectable:
            self._details["connector"] = connector

    @callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        return async_track_time_interval(
            self.hass, self._async_expire_devices, timedelta(seconds=30)
        )

    def _async_expire_devices(self, _datetime: datetime.datetime) -> None:
        """Expire old devices."""
        now = time.monotonic()
        expired = [
            address
            for address, timestamp in self._discovered_device_timestamps.items()
            if now - timestamp > FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
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

    @callback
    def async_on_advertisement(self, adv: BluetoothLEAdvertisement) -> None:
        """Call the registered callback."""
        now = monotonic_time_coarse()
        address = ":".join(TWO_CHAR.findall("%012X" % adv.address))  # must be upper
        name = adv.name
        if prev_discovery := self._discovered_device_advertisement_datas.get(address):
            # If the last discovery had the full local name
            # and this one doesn't, keep the old one as we
            # always want the full local name over the short one
            prev_device = prev_discovery[0]
            if len(prev_device.name) > len(adv.name):
                name = prev_device.name

        advertisement_data = AdvertisementData(
            local_name=None if name == "" else name,
            manufacturer_data=adv.manufacturer_data,
            service_data=adv.service_data,
            service_uuids=adv.service_uuids,
            rssi=adv.rssi,
            tx_power=-127,
            platform_data=(),
        )
        device = BLEDevice(  # type: ignore[no-untyped-call]
            address=address,
            name=name,
            details=self._details,
            rssi=adv.rssi,  # deprecated, will be removed in newer bleak
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
                rssi=adv.rssi,
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
