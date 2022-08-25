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
        21: b"\x00\x00\xf0\x05\x00\x00\xd7n\xbe\x01e\x00\x00\x00\xa7\x01\x00\x00\x00\x00"
    },
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    source="local",
)
