"""Tests for the ThermoBeacon integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_THERMOBEACON_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

THERMOBEACON_SERVICE_INFO = BluetoothServiceInfo(
    name="ThermoBeacon",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={},
    manufacturer_data={
        16: b"\x00\x00\xb0\x02\x00\x00G\xa4\xe2\x0c\x80\x01\xb6\x02J\x00\x00\x00"
    },
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    source="local",
)
