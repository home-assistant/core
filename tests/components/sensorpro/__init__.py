"""Tests for the SensorPro integration."""


from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_SENSORPRO_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

SENSORPRO_SERVICE_INFO = BluetoothServiceInfo(
    name="T201",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={},
    manufacturer_data={
        43605: b"\x01\x01\xa4\xc18.\xcan\x01\x07\n\x02\x13\x9dd\x00\x01\x01\x01\xa4\xc18.\xcan\x01\x07\n\x02\x13\x9dd\x00\x01"
    },
    service_uuids=[],
    source="local",
)
