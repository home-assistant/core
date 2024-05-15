"""Parser for OpenBLESensors BLE advertisements.

This file is shamelessly copied from the following repository:
https://github.com/Ernst79/bleparser/blob/c42ae922e1abed2720c7fac993777e1bd59c0c93/package/bleparser/bluemaestro.py

MIT License applies.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from bluetooth_data_tools import short_address
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import SensorLibrary

from .const import MFR

_LOGGER = logging.getLogger(__name__)


@dataclass
class OpenBLESensorsDevice:
    model: str


DEVICE_TYPES = {
    0xC0: OpenBLESensorsDevice("PSS CFG Beacon"),
    0xD0: OpenBLESensorsDevice("Soil Sensor"),
}

MFR_ID = 0x0877


class OpenBLESensorsBluetoothDeviceData(BluetoothData):
    """Date update for OpenBLESensors Bluetooth devices."""

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing bluemaestro BLE advertisement data: %s", service_info)
        if MFR_ID not in service_info.manufacturer_data:
            return
        changed_manufacturer_data = self.changed_manufacturer_data(service_info)

        if not changed_manufacturer_data or len(changed_manufacturer_data) > 1:
            # If len(changed_manufacturer_data) > 1 it means we switched
            # ble adapters so we do not know which data is the latest
            # and we need to wait for the next update.
            return
        data = changed_manufacturer_data[MFR_ID]

        device_id = data[0]
        if device_id not in DEVICE_TYPES:
            return
        device = DEVICE_TYPES[device_id]
        name = device_type = device.model
        self.set_precision(2)
        self.set_device_type(device_type)
        self.set_title(f"{name} {short_address(service_info.address)}")
        self.set_device_name(f"{name} {short_address(service_info.address)}")
        self.set_device_manufacturer(MFR)

        batt = service_info.manufacturer_data[2167][3]
        self.update_predefined_sensor(SensorLibrary.BATTERY__PERCENTAGE, batt)
        self.update_predefined_sensor(SensorLibrary.IMPEDANCE__OHM, 0)
        # self.update_predefined_sensor(SensorLibrary.TEMPERATURE__CELSIUS, temp / 10)
        # self.update_predefined_sensor(SensorLibrary.HUMIDITY__PERCENTAGE, humi / 10)
