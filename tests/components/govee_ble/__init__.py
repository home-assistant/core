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

GVH5106_SERVICE_INFO = BluetoothServiceInfo(
    name="GVH5106_4E05",
    address="CC:32:37:35:4E:05",
    rssi=-66,
    manufacturer_data={1: b"\x01\x01\x0e\xd12\x98"},
    service_uuids=["0000ec88-0000-1000-8000-00805f9b34fb"],
    service_data={},
    source="local",
)


GV5125_BUTTON_0_SERVICE_INFO = BluetoothServiceInfo(
    name="GV51255367",
    address="C1:37:37:32:0F:45",
    rssi=-36,
    manufacturer_data={
        60552: b"\x01\n.\xaf\xd9085Sg\x01\x01",
        61320: b".\xaf\x00\x00b\\\xae\x92\x15\xb6\xa8\n\xd4\x81K\xcaK_s\xd9E40\x02",
    },
    service_data={},
    service_uuids=[],
    source="24:4C:AB:03:E6:B8",
)

GV5125_BUTTON_1_SERVICE_INFO = BluetoothServiceInfo(
    name="GV51255367",
    address="C1:37:37:32:0F:45",
    rssi=-36,
    manufacturer_data={
        60552: b"\x01\n.\xaf\xd9085Sg\x01\x01",
        61320: b".\xaf\x00\x00\xfb\x0e\xc9h\xd7\x05l\xaf*\xf3\x1b\xe8w\xf1\xe1\xe8\xe3\xa7\xf8\xc6",
    },
    service_data={},
    service_uuids=[],
    source="24:4C:AB:03:E6:B8",
)


GV5121_MOTION_SERVICE_INFO = BluetoothServiceInfo(
    name="GV5121195A",
    address="C1:37:37:32:0F:45",
    rssi=-36,
    manufacturer_data={
        61320: b"Y\x94\x00\x00\xf0\xb9\x197\xaeP\xb67,\x86j\xc2\xf3\xd0a\xe7\x17\xc0,\xef"
    },
    service_data={},
    service_uuids=[],
    source="24:4C:AB:03:E6:B8",
)


GV5121_MOTION_SERVICE_INFO_2 = BluetoothServiceInfo(
    name="GV5121195A",
    address="C1:37:37:32:0F:45",
    rssi=-36,
    manufacturer_data={
        61320: b"Y\x94\x00\x06\xa3f6e\xc8\xe6\xfdv\x04\xaf\xe7k\xbf\xab\xeb\xbf\xb3\xa3\xd5\x19"
    },
    service_data={},
    service_uuids=[],
    source="24:4C:AB:03:E6:B8",
)


GV5123_OPEN_SERVICE_INFO = BluetoothServiceInfo(
    name="GV51230B3D",
    address="C1:37:37:32:0F:45",
    rssi=-36,
    manufacturer_data={
        61320: b"=\xec\x00\x00\xdeCw\xd5^U\xf9\x91In6\xbd\xc6\x7f\x8b,'\x06t\x97"
    },
    service_data={},
    service_uuids=[],
    source="24:4C:AB:03:E6:B8",
)


GV5123_CLOSED_SERVICE_INFO = BluetoothServiceInfo(
    name="GV51230B3D",
    address="C1:37:37:32:0F:45",
    rssi=-36,
    manufacturer_data={
        61320: b"=\xec\x00\x01Y\xdbk\xd9\xbe\xd7\xaf\xf7*&\xaaK\xd7-\xfa\x94W>[\xe9"
    },
    service_data={},
    service_uuids=[],
    source="24:4C:AB:03:E6:B8",
)


GVH5124_SERVICE_INFO = BluetoothServiceInfo(
    name="GV51242F68",
    address="D3:32:39:37:2F:68",
    rssi=-67,
    manufacturer_data={
        61320: b"\x08\xa2\x00\x01%\xc2YW\xfdzu\x0e\xf24\xa2\x18\xbb\x15F|[s{\x04"
    },
    service_data={},
    service_uuids=[],
    source="local",
)

GVH5124_2_SERVICE_INFO = BluetoothServiceInfo(
    name="GV51242F68",
    address="D3:32:39:37:2F:68",
    rssi=-67,
    manufacturer_data={
        61320: b"\x08\xa2\x00\x13^Sso\xaeC\x9aU\xcf\xd8\x02\x1b\xdf\xd5\xded;+\xd6\x13"
    },
    service_data={},
    service_uuids=[],
    source="local",
)


GVH5127_MOTION_SERVICE_INFO = BluetoothServiceInfo(
    name="GVH51275E3F",
    address="D0:C9:07:1B:5E:3F",
    rssi=-61,
    manufacturer_data={34819: b"\xec\x00\x01\x01\x01\x11"},
    service_data={},
    service_uuids=[],
    source="Core Bluetooth",
)
GVH5127_PRESENT_SERVICE_INFO = BluetoothServiceInfo(
    name="GVH51275E3F",
    address="D0:C9:07:1B:5E:3F",
    rssi=-60,
    manufacturer_data={34819: b"\xec\x00\x01\x01\x01\x01"},
    service_data={},
    service_uuids=[],
    source="Core Bluetooth",
)
GVH5127_ABSENT_SERVICE_INFO = BluetoothServiceInfo(
    name="GVH51275E3F",
    address="D0:C9:07:1B:5E:3F",
    rssi=-53,
    manufacturer_data={34819: b"\xec\x00\x01\x01\x00\x00"},
    service_data={},
    service_uuids=[],
    source="Core Bluetooth",
)
