"""Tests for the SensorPush integration."""
from sensorpush_ble import (
    DeviceClass,
    DeviceKey,
    SensorDescription,
    SensorDeviceInfo,
    SensorUpdate,
    SensorValue,
    Units,
)

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_SENSOR_PUSH_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

HTW_SERVICE_INFO = BluetoothServiceInfo(
    name="SensorPush HT.w 0CA1",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={11271: b"\xfe\x00\x01"},
    service_data={},
    service_uuids=["ef090000-11d6-42ba-93b8-9dd7ec090ab0"],
    source="local",
)
HTW_SENSOR_UPDATE = SensorUpdate(
    title=None,
    devices={
        None: SensorDeviceInfo(
            model="HTP.w",
            manufacturer="SensorPush",
            name="HTP.w 0CA1",
            sw_version=None,
            hw_version=None,
        )
    },
    entity_descriptions={
        DeviceKey(key="temperature", device_id=None): SensorDescription(
            device_key=DeviceKey(key="temperature", device_id=None),
            device_class=DeviceClass.TEMPERATURE,
            native_unit_of_measurement=Units.TEMP_CELSIUS,
        ),
        DeviceKey(key="humidity", device_id=None): SensorDescription(
            device_key=DeviceKey(key="humidity", device_id=None),
            device_class=DeviceClass.HUMIDITY,
            native_unit_of_measurement=Units.PERCENTAGE,
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorDescription(
            device_key=DeviceKey(key="signal_strength", device_id=None),
            device_class=DeviceClass.SIGNAL_STRENGTH,
            native_unit_of_measurement=Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        ),
    },
    entity_values={
        DeviceKey(key="temperature", device_id=None): SensorValue(
            device_key=DeviceKey(key="temperature", device_id=None),
            native_value=20.21,
            name="Temperature",
        ),
        DeviceKey(key="humidity", device_id=None): SensorValue(
            device_key=DeviceKey(key="humidity", device_id=None),
            native_value=45.08,
            name="Humidity",
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorValue(
            device_key=DeviceKey(key="signal_strength", device_id=None),
            name="Signal Strength",
            native_value=-60,
        ),
    },
)
HTPWX_SERVICE_INFO = BluetoothServiceInfo(
    name="SensorPush HTP.xw F4D",
    address="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    rssi=-56,
    manufacturer_data={7168: b"\xcd=!\xd1\xb9"},
    service_data={},
    service_uuids=["ef090000-11d6-42ba-93b8-9dd7ec090ab0"],
    source="local",
)
HTPWX_SENSOR_UPDATE = SensorUpdate(
    title=None,
    devices={
        None: SensorDeviceInfo(
            model="HTP.xw",
            manufacturer="SensorPush",
            name="HTP.xw F4D",
            sw_version=None,
            hw_version=None,
        )
    },
    entity_descriptions={
        DeviceKey(key="temperature", device_id=None): SensorDescription(
            device_key=DeviceKey(key="temperature", device_id=None),
            device_class=DeviceClass.TEMPERATURE,
            native_unit_of_measurement=Units.TEMP_CELSIUS,
        ),
        DeviceKey(key="humidity", device_id=None): SensorDescription(
            device_key=DeviceKey(key="humidity", device_id=None),
            device_class=DeviceClass.HUMIDITY,
            native_unit_of_measurement=Units.PERCENTAGE,
        ),
        DeviceKey(key="pressure", device_id=None): SensorDescription(
            device_key=DeviceKey(key="pressure", device_id=None),
            device_class=DeviceClass.PRESSURE,
            native_unit_of_measurement=Units.PRESSURE_MBAR,
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorDescription(
            device_key=DeviceKey(key="signal_strength", device_id=None),
            device_class=DeviceClass.SIGNAL_STRENGTH,
            native_unit_of_measurement=Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        ),
    },
    entity_values={
        DeviceKey(key="temperature", device_id=None): SensorValue(
            device_key=DeviceKey(key="temperature", device_id=None),
            native_value=20.34,
            name="Temperature",
        ),
        DeviceKey(key="humidity", device_id=None): SensorValue(
            device_key=DeviceKey(key="humidity", device_id=None),
            native_value=46.27,
            name="Humidity",
        ),
        DeviceKey(key="pressure", device_id=None): SensorValue(
            device_key=DeviceKey(key="pressure", device_id=None),
            native_value=1009.21,
            name="Pressure",
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorValue(
            device_key=DeviceKey(key="signal_strength", device_id=None),
            native_value=-55,
            name="Signal Strength",
        ),
    },
)
