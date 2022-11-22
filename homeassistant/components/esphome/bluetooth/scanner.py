"""Bluetooth scanner for esphome."""
from __future__ import annotations

import re

from aioesphomeapi import BluetoothLEAdvertisement

from homeassistant.components.bluetooth import BaseHaRemoteScanner
from homeassistant.core import callback

TWO_CHAR = re.compile("..")


class ESPHomeScanner(BaseHaRemoteScanner):
    """Scanner for esphome."""

    @callback
    def async_on_advertisement(self, adv: BluetoothLEAdvertisement) -> None:
        """Call the registered callback."""
        address = ":".join(TWO_CHAR.findall("%012X" % adv.address))  # must be upper
        self._async_on_advertisement(
            address,
            adv.rssi,
            adv.name,
            adv.service_uuids,
            adv.service_data,
            adv.manufacturer_data,
            None,
        )
