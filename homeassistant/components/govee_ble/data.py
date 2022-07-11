"""Parser for Govee BLE advertisements."""
from __future__ import annotations

import logging

from bleparser.govee import parse_govee

from homeassistant.components.ble_parser import async_get_manufacturer_parser
from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.components.bluetooth.device import BluetoothDeviceData

_LOGGER = logging.getLogger(__name__)


NOT_GOVEE_MANUFACTURER = {76}


class GoveeBluetoothDeviceData(BluetoothDeviceData):
    """Data for Govee BLE sensors."""

    def __init__(self) -> None:
        """Init the GoveeBluetoothDeviceData."""
        super().__init__()
        self.parser = async_get_manufacturer_parser(self, parse_govee)

    def update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        if service_info.name.startswith("GV"):
            self.set_device_name(service_info.name[2:])
        for mgr_id in service_info.manufacturer_data:
            if mgr_id not in NOT_GOVEE_MANUFACTURER:
                self.parser.async_load_manufacturer_data_id(service_info, mgr_id)
