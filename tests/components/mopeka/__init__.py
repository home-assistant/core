"""Tests for the Mopeka integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_MOPEKA_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

PRO_SERVICE_INFO = BluetoothServiceInfo(
    name="",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    manufacturer_data={89: b"\x08rF\x00@\xe0\xf5\t\xf0\xd8"},
    service_data={},
    service_uuids=["0000fee5-0000-1000-8000-00805f9b34fb"],
    source="local",
)

PRO_UNUSABLE_SIGNAL_SERVICE_INFO = BluetoothServiceInfo(
    name="",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    manufacturer_data={89: b"\x08rF\x00\x00\xe0\xf5\t\xf0\xd8"},
    service_data={},
    service_uuids=["0000fee5-0000-1000-8000-00805f9b34fb"],
    source="local",
)


PRO_GOOD_SIGNAL_SERVICE_INFO = BluetoothServiceInfo(
    name="",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    manufacturer_data={89: b"\x08pC\xb6\xc3\xe0\xf5\t\xfa\xe3"},
    service_data={},
    service_uuids=["0000fee5-0000-1000-8000-00805f9b34fb"],
    source="local",
)
