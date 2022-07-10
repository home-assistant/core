"""Parser for SensorPush BLE advertisements."""
from __future__ import annotations

import logging

from bleparser.sensorpush import parse_sensorpush

from homeassistant.components.ble_parser import async_get_manufacturer_parser
from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.components.bluetooth.device import BluetoothDeviceData

_LOGGER = logging.getLogger(__name__)


class SensorPushBluetoothDeviceData(BluetoothDeviceData):
    """Date update for SensorPush Bluetooth devices."""

    def __init__(self) -> None:
        """Init the SensorPushBluetoothDeviceData."""
        super().__init__()
        self.parser = async_get_manufacturer_parser(self, parse_sensorpush)

    def update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        manufacturer_data = service_info.manufacturer_data
        _LOGGER.debug(
            "Parsing SensorPush BLE advertisement data: %s", manufacturer_data
        )
        if service_info.name.startswith("SensorPush "):
            self.set_device_name(service_info.name[11:])
        else:
            self.set_device_name(service_info.name)
        self.parser.async_load_newest_manufacturer_data(service_info)
