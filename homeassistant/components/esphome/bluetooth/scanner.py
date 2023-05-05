"""Bluetooth scanner for esphome."""
from __future__ import annotations

from aioesphomeapi import BluetoothLEAdvertisement
from bluetooth_data_tools import int_to_bluetooth_address

from homeassistant.components.bluetooth import BaseHaRemoteScanner
from homeassistant.core import callback


class ESPHomeScanner(BaseHaRemoteScanner):
    """Scanner for esphome."""

    @callback
    def async_on_advertisement(self, adv: BluetoothLEAdvertisement) -> None:
        """Call the registered callback."""
        # The mac address is a uint64, but we need a string
        self._async_on_advertisement(
            int_to_bluetooth_address(adv.address),
            adv.rssi,
            adv.name,
            adv.service_uuids,
            adv.service_data,
            adv.manufacturer_data,
            None,
            {"address_type": adv.address_type},
        )
