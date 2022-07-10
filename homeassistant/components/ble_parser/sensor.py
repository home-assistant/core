"""The BLE Parser integration sensor mappings."""
from __future__ import annotations

from typing import Final, TypedDict

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_NAME,
    PERCENTAGE,
    PRESSURE_MBAR,
    TEMP_CELSIUS,
)

ATTR_NATIVE_UNIT_OF_MEASUREMENT: Final = "native_unit_of_measurement"


class SensorMapping(TypedDict):
    """Sensor mapping."""

    native_unit_of_measurement: str
    state_class: SensorStateClass
    device_class: SensorDeviceClass
    name: str | None


MAPPINGS = {
    "temperature": SensorMapping(
        {
            ATTR_NATIVE_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
            ATTR_NAME: None,
        }
    ),
    "humidity": SensorMapping(
        {
            ATTR_NATIVE_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
            ATTR_NAME: None,
        }
    ),
    "pressure": SensorMapping(
        {
            ATTR_NATIVE_UNIT_OF_MEASUREMENT: PRESSURE_MBAR,
            ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
            ATTR_NAME: None,
        }
    ),
    "battery": SensorMapping(
        {
            ATTR_NATIVE_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_DEVICE_CLASS: SensorDeviceClass.BATTERY,
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
            ATTR_NAME: None,
        }
    ),
}

for probe_id in range(1, 6):
    for probe_type, probe_name in ("probe", "Probe"), ("alarm probe", "Alarm Probe"):
        MAPPINGS[f"temperature {probe_type} {probe_id}"] = SensorMapping(
            {
                ATTR_NATIVE_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_NAME: f"Temperature {probe_name} {probe_id}",
            }
        )
