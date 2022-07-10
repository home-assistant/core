"""The BLE Parser integration sensor mappings."""
from __future__ import annotations

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

ATTR_NATIVE_UNIT_OF_MEASUREMENT = "native_unit_of_measurement"

TEMP_SENSOR_BASE_MAPPING = {
    ATTR_NATIVE_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
    ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
    ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
}

MAPPINGS = {
    "temperature": TEMP_SENSOR_BASE_MAPPING,
    "humidity": {
        ATTR_NATIVE_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    "pressure": {
        ATTR_NATIVE_UNIT_OF_MEASUREMENT: PRESSURE_MBAR,
        ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
}

for probe_id in range(1, 6):
    MAPPINGS[f"temperature probe {probe_id}"] = {
        **TEMP_SENSOR_BASE_MAPPING,
        ATTR_NAME: f"Temperature Probe {probe_id}",
    }
    MAPPINGS[f"temperature alarm probe {probe_id}"] = {
        **TEMP_SENSOR_BASE_MAPPING,
        ATTR_NAME: f"Temperature Alarm Probe {probe_id}",
    }
