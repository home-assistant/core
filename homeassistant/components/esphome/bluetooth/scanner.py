"""Bluetooth scanner for esphome."""
from __future__ import annotations

import re
from typing import Any

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
            {"address_type": adv.address_type},
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
