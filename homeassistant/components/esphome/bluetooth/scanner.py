"""Bluetooth scanner for esphome."""
from __future__ import annotations

from aioesphomeapi import BluetoothLEAdvertisement

from homeassistant.components.bluetooth import BaseHaRemoteScanner
from homeassistant.core import callback


class ESPHomeScanner(BaseHaRemoteScanner):
    """Scanner for esphome."""

    @callback
    def async_on_advertisement(self, adv: BluetoothLEAdvertisement) -> None:
        """Call the registered callback."""
        # The mac address is a uint64, but we need a string
        mac_hex = f"{adv.address:012X}"
        self._async_on_advertisement(
            f"{mac_hex[0:2]}:{mac_hex[2:4]}:{mac_hex[4:6]}:{mac_hex[6:8]}:{mac_hex[8:10]}:{mac_hex[10:12]}",
            adv.rssi,
            adv.name,
            adv.service_uuids,
            adv.service_data,
            adv.manufacturer_data,
            None,
            {"address_type": adv.address_type},
        )
