"""Tests for the Govee BLE integration."""


from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_GOVEE_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

GVH5075_SERVICE_INFO = BluetoothServiceInfo(
    name="GVH5075 2762",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={
        60552: b"\x00\x03A\xc2d\x00L\x00\x02\x15INTELLI_ROCKS_HWPu\xf2\xff\x0c"
    },
    service_uuids=["0000ec88-0000-1000-8000-00805f9b34fb"],
    service_data={},
    source="local",
)

GVH5177_SERVICE_INFO = BluetoothServiceInfo(
    name="GVH5177 2EC8",
    address="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    rssi=-56,
    manufacturer_data={
        1: b"\x01\x01\x036&dL\x00\x02\x15INTELLI_ROCKS_HWQw\xf2\xff\xc2"
    },
    service_uuids=["0000ec88-0000-1000-8000-00805f9b34fb"],
    service_data={},
    source="local",
)

GVH5178_REMOTE_SERVICE_INFO = BluetoothServiceInfo(
    name="B51782BC8",
    address="A4:C1:38:75:2B:C8",
    rssi=-66,
    manufacturer_data={
        1: b"\x01\x01\x01\x00\x2a\xf7\x64\x00\x03",
        76: b"\x02\x15INTELLI_ROCKS_HWPu\xf2\xff\xc2",
    },
    service_data={},
    service_uuids=["0000ec88-0000-1000-8000-00805f9b34fb"],
    source="local",
)
GVH5178_PRIMARY_SERVICE_INFO = BluetoothServiceInfo(
    name="B51782BC8",
    address="A4:C1:38:75:2B:C8",
    rssi=-66,
    manufacturer_data={
        1: b"\x01\x01\x00\x00\x2a\xf7\x64\x00\x03",
        76: b"\x02\x15INTELLI_ROCKS_HWPu\xf2\xff\xc2",
    },
    service_data={},
    service_uuids=["0000ec88-0000-1000-8000-00805f9b34fb"],
    source="local",
)

GVH5178_SERVICE_INFO_ERROR = BluetoothServiceInfo(
    name="B51782BC8",
    address="A4:C1:38:75:2B:C8",
    rssi=-66,
    manufacturer_data={
        1: b"\x01\x01\x01\x00\x03\xe7\xe4\x00\x01",
        76: b"\x02\x15INTELLI_ROCKS_HWPu\xf2\xff\xc2",
    },
    service_data={},
    service_uuids=["0000ec88-0000-1000-8000-00805f9b34fb"],
    source="local",
)
