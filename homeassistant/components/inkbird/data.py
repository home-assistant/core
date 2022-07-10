"""Parser for INKBIRD BLE advertisements.

This file is shamlessly copied from the following repository:
https://github.com/Ernst79/bleparser/blob/c42ae922e1abed2720c7fac993777e1bd59c0c93/package/bleparser/inkbird.py

MIT License applies.
"""
from __future__ import annotations

import logging
from struct import unpack

from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.components.bluetooth.device import BluetoothDeviceData
from homeassistant.components.bluetooth.sensor import BluetoothSensorType
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS

_LOGGER = logging.getLogger(__name__)


BBQ_LENGTH_TO_TYPE = {
    10: ("iBBQ-1", "<h"),
    12: ("iBBQ-2", "<HH"),
    16: ("iBBQ-4", "<hhhh"),
    20: ("iBBQ-6", "<hhhhhh"),
}


def convert_temperature(temp: float) -> float:
    """Temperature converter."""
    if temp > 0:
        return temp / 10.0
    return 0


class INKBIRDBluetoothDeviceData(BluetoothDeviceData):
    """Date update for INKBIRD Bluetooth devices."""

    def update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing inkbird BLE advertisement data: %s", service_info)
        manufacturer_data = service_info.manufacturer_data
        local_name = service_info.name
        if local_name == "sps":
            self.set_device_type("IBS-TH")
        elif local_name == "tps":
            self.set_device_type("IBS-TH2/P01B")
        if not manufacturer_data:
            return
        last_id = list(manufacturer_data)[-1]
        data = int(last_id).to_bytes(2, byteorder="little") + manufacturer_data[last_id]
        self._process_update(service_info.name, data)

    def _process_update(self, complete_local_name: str, data: bytes) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing INKBIRD BLE advertisement data: %s", data)
        msg_length = len(data)

        if msg_length == 9:
            (temp, hum) = unpack("<hH", data[0:4])
            bat = int.from_bytes(data[7:8], "little")
            if complete_local_name == "sps":
                self.update_predefined_sensor(
                    BluetoothSensorType.TEMPERATURE, TEMP_CELSIUS, temp / 100
                )
                self.update_predefined_sensor(
                    BluetoothSensorType.HUMIDITY, PERCENTAGE, hum / 100
                )
                self.update_predefined_sensor(
                    BluetoothSensorType.BATTERY, PERCENTAGE, bat
                )
            elif complete_local_name == "tps":
                self.update_predefined_sensor(
                    BluetoothSensorType.TEMPERATURE, TEMP_CELSIUS, temp / 100
                )
                self.update_predefined_sensor(
                    BluetoothSensorType.BATTERY, PERCENTAGE, bat
                )
            return

        if bbq_data := BBQ_LENGTH_TO_TYPE.get(msg_length):
            # TODO: do we need the source mac check here?
            # Apple devices have a UUID in the advertisement data
            dev_type, unpack_str = bbq_data
            self.set_device_type(dev_type)
            xvalue = data[8:]
            for idx, temp in enumerate(unpack(unpack_str, xvalue)):
                num = idx + 1
                self.update_sensor(
                    key=f"temperature_probe_{num}",
                    native_unit_of_measurement=TEMP_CELSIUS,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_value=convert_temperature(temp),
                    name=f"Temperature Probe {num}",
                )
