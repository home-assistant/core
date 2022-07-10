"""Parser for INKBIRD BLE advertisements."""
from __future__ import annotations

import logging

from bleparser.inkbird import parse_inkbird

from homeassistant.components.ble_parser import async_get_parser_with_local_name
from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.components.bluetooth.device import BluetoothDeviceData

_LOGGER = logging.getLogger(__name__)

LOCAL_NAMES_TO_DEVICE_TYPE = {"sps": "IBS-TH", "tps": "IBS-TH2/P01B"}


class INKBIRDBluetoothDeviceData(BluetoothDeviceData):
    """Date update for INKBIRD Bluetooth devices."""

    def __init__(self) -> None:
        """Init the INKBIRDBluetoothDeviceData."""
        super().__init__()
        self.parser = async_get_parser_with_local_name(self, parse_inkbird)

    def update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing inkbird BLE advertisement data: %s", service_info)
        if device_type := LOCAL_NAMES_TO_DEVICE_TYPE.get(service_info.name):
            self.set_device_type(device_type)
        self.parser.async_load_manufacturer_data(service_info)
