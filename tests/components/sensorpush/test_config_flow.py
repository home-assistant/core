"""Test the SensorPush config flow."""

from sensorpush_ble import (
    DeviceClass,
    DeviceKey,
    SensorDescription,
    SensorUpdate,
    SensorValue,
)

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

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
        None: {"model": "HT.w", "manufacturer": "SensorPush", "name": "HT.w 0CA1"}
    },
    entity_descriptions={
        DeviceKey(key="temperature", device_id=None): SensorDescription(
            device_key=DeviceKey(key="temperature", device_id=None),
            name="Temperature",
            device_class=DeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
        ),
        DeviceKey(key="humidity", device_id=None): SensorDescription(
            device_key=DeviceKey(key="humidity", device_id=None),
            name="Humidity",
            device_class=DeviceClass.HUMIDITY,
            native_unit_of_measurement="%",
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorDescription(
            device_key=DeviceKey(key="signal_strength", device_id=None),
            name="Signal Strength",
            device_class=DeviceClass.SIGNAL_STRENGTH,
            native_unit_of_measurement="dBm",
        ),
    },
    entity_values={
        DeviceKey(key="temperature", device_id=None): SensorValue(
            device_key=DeviceKey(key="temperature", device_id=None), native_value=20.21
        ),
        DeviceKey(key="humidity", device_id=None): SensorValue(
            device_key=DeviceKey(key="humidity", device_id=None), native_value=45.08
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorValue(
            device_key=DeviceKey(key="signal_strength", device_id=None),
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
        None: {"model": "HTP.xw", "manufacturer": "SensorPush", "name": "HTP.xw F4D"}
    },
    entity_descriptions={
        DeviceKey(key="temperature", device_id=None): SensorDescription(
            device_key=DeviceKey(key="temperature", device_id=None),
            name="Temperature",
            device_class=DeviceClass.TEMPERATURE,
            native_unit_of_measurement="°C",
        ),
        DeviceKey(key="humidity", device_id=None): SensorDescription(
            device_key=DeviceKey(key="humidity", device_id=None),
            name="Humidity",
            device_class=DeviceClass.HUMIDITY,
            native_unit_of_measurement="%",
        ),
        DeviceKey(key="pressure", device_id=None): SensorDescription(
            device_key=DeviceKey(key="pressure", device_id=None),
            name="Pressure",
            device_class=DeviceClass.PRESSURE,
            native_unit_of_measurement="Pa",
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorDescription(
            device_key=DeviceKey(key="signal_strength", device_id=None),
            name="Signal Strength",
            device_class=DeviceClass.SIGNAL_STRENGTH,
            native_unit_of_measurement="dBm",
        ),
    },
    entity_values={
        DeviceKey(key="temperature", device_id=None): SensorValue(
            device_key=DeviceKey(key="temperature", device_id=None), native_value=20.34
        ),
        DeviceKey(key="humidity", device_id=None): SensorValue(
            device_key=DeviceKey(key="humidity", device_id=None), native_value=46.27
        ),
        DeviceKey(key="pressure", device_id=None): SensorValue(
            device_key=DeviceKey(key="pressure", device_id=None), native_value=1009.21
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorValue(
            device_key=DeviceKey(key="signal_strength", device_id=None),
            native_value=-55,
        ),
    },
)


def test_async_step_bluetooth(hass):
    """Test discovery via bluetooth."""
