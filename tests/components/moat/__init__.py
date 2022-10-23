"""Tests for the Moat BLE integration."""


from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_MOAT_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

MOAT_S2_SERVICE_INFO = BluetoothServiceInfo(
    name="Moat_S2",
    manufacturer_data={},
    service_data={
        "00005000-0000-1000-8000-00805f9b34fb": b"\xdfy\xe3\xa6\x12\xb3\xf5\x0b",
        "00001000-0000-1000-8000-00805f9b34fb": (
            b"\xdfy\xe3\xa6\x12\xb3\x11S\xdbb\xfcbpq" b"\xf5\x0b\xff\xff"
        ),
    },
    service_uuids=[
        "00001000-0000-1000-8000-00805f9b34fb",
        "00002000-0000-1000-8000-00805f9b34fb",
    ],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    source="local",
)
