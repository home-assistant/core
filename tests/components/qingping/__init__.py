"""Tests for the Qingping integration."""


from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_QINGPING_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

LIGHT_AND_SIGNAL_SERVICE_INFO = BluetoothServiceInfo(
    name="Qingping Motion & Light",
    manufacturer_data={},
    service_uuids=[],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={
        "0000fdcd-0000-1000-8000-00805f9b34fb": b"H\x12"
        b"\xcd\xd5`4-X\x08\x04\x00\r\x00\x00\x0f\x01\xee"
    },
    source="local",
)


NO_DATA_SERVICE_INFO = BluetoothServiceInfo(
    name="Qingping Motion & Light",
    manufacturer_data={},
    service_uuids=[],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={
        "0000fdcd-0000-1000-8000-00805f9b34fb": b"0X\x83\n\x02\xcd\xd5`4-X\x08"
    },
    source="local",
)
