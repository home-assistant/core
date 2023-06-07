"""Bluetooth scanner for esphome."""
from __future__ import annotations

from aioesphomeapi import BluetoothLEAdvertisement, BluetoothLERawAdvertisement
from bluetooth_data_tools import int_to_bluetooth_address, parse_advertisement_data

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

    @callback
    def async_on_raw_advertisements(
        self, advertisements: list[BluetoothLERawAdvertisement]
    ) -> None:
        """Call the registered callback."""
        # [BluetoothLERawAdvertisement(address=92997118468307, rssi=-64, address_type=1, data=b'\x03\x03\x9f\xfe\x17\x16\x9f\xfe\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'), BluetoothLERawAdvertisement(address=277856570910367, rssi=-60, address_type=1, data=b'\x02\x01\x06\t\xffY\x00\xfc\xb5\x865&\x9f')]
        for adv in advertisements:
            parsed = parse_advertisement_data(adv.data)
            self._async_on_advertisement(
                int_to_bluetooth_address(adv.address),
                adv.rssi,
                parsed.local_name,
                parsed.service_uuids,
                parsed.service_data,
                parsed.manufacturer_data,
                None,
                {"address_type": adv.address_type},
            )
