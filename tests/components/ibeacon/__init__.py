"""Tests for the ibeacon integration."""
from typing import Any

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.components.bluetooth import generate_ble_device

BLUECHARM_BLE_DEVICE = generate_ble_device(
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    name="BlueCharm_177999",
)
BLUECHARM_BEACON_SERVICE_INFO = BluetoothServiceInfo(
    name="BlueCharm_177999",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    service_data={},
    manufacturer_data={76: b"\x02\x15BlueCharmBeacons\x0e\xfe\x13U\xc5"},
    service_uuids=[],
    source="local",
)
BLUECHARM_BEACON_SERVICE_INFO_2 = BluetoothServiceInfo(
    name="BlueCharm_177999",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-53,
    manufacturer_data={76: b"\x02\x15BlueCharmBeacons\x0e\xfe\x13U\xc5"},
    service_data={
        "00002080-0000-1000-8000-00805f9b34fb": b"j\x0c\x0e\xfe\x13U",
        "0000feaa-0000-1000-8000-00805f9b34fb": b" \x00\x0c\x00\x1c\x00\x00\x00\x06h\x00\x008\x10",
    },
    service_uuids=["0000feaa-0000-1000-8000-00805f9b34fb"],
    source="local",
)
BLUECHARM_BEACON_SERVICE_INFO_DBUS = BluetoothServiceInfo(
    name="BlueCharm_177999",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-63,
    service_data={},
    manufacturer_data={76: b"\x02\x15BlueCharmBeacons\x0e\xfe\x13U\xc5"},
    service_uuids=[],
    source="local",
)
NO_NAME_BEACON_SERVICE_INFO = BluetoothServiceInfo(
    name="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-53,
    manufacturer_data={76: b"\x02\x15NoNamearmBeacons\x0e\xfe\x13U\xc5"},
    service_data={
        "00002080-0000-1000-8000-00805f9b34fb": b"j\x0c\x0e\xfe\x13U",
        "0000feaa-0000-1000-8000-00805f9b34fb": b" \x00\x0c\x00\x1c\x00\x00\x00\x06h\x00\x008\x10",
    },
    service_uuids=["0000feaa-0000-1000-8000-00805f9b34fb"],
    source="local",
)
BEACON_RANDOM_ADDRESS_SERVICE_INFO = BluetoothServiceInfo(
    name="RandomAddress_1234",
    address="AA:BB:CC:DD:EE:00",
    rssi=-63,
    service_data={},
    manufacturer_data={76: b"\x02\x15RandCharmBeacons\x0e\xfe\x13U\xc5"},
    service_uuids=[],
    source="local",
)
TESLA_TRANSIENT = BluetoothServiceInfo(
    address="CC:CC:CC:CC:CC:CC",
    rssi=-60,
    name="S6da7c9389bd5452cC",
    manufacturer_data={
        76: b"\x02\x15t'\x8b\xda\xb6DE \x8f\x0cr\x0e\xaf\x05\x995\x00\x00[$\xc5"
    },
    service_data={},
    service_uuids=[],
    source="hci0",
)
TESLA_TRANSIENT_BLE_DEVICE = generate_ble_device(
    address="CC:CC:CC:CC:CC:CC",
    name="S6da7c9389bd5452cC",
)

FEASY_BEACON_BLE_DEVICE = generate_ble_device(
    address="AA:BB:CC:DD:EE:FF",
    name="FSC-BP108",
)

FEASY_BEACON_SERVICE_INFO_1 = BluetoothServiceInfo(
    name="FSC-BP108",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-63,
    manufacturer_data={
        76: b"\x02\x15\xfd\xa5\x06\x93\xa4\xe2O\xb1\xaf\xcf\xc6\xeb\x07dx%'Qe\xc1\xfd"
    },
    service_data={
        "0000feaa-0000-1000-8000-00805f9b34fb": b' \x00\x0c\x86\x80\x00\x00\x00\x93f\x0b\x7f\x93"',
        "0000fff0-0000-1000-8000-00805f9b34fb": b"'\x02\x17\x92\xdc\r0\x0e \xbad",
    },
    service_uuids=[
        "0000feaa-0000-1000-8000-00805f9b34fb",
        "0000fef5-0000-1000-8000-00805f9b34fb",
    ],
    source="local",
)


FEASY_BEACON_SERVICE_INFO_2 = BluetoothServiceInfo(
    name="FSC-BP108",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-63,
    manufacturer_data={
        76: b"\x02\x15\xd5F\xdf\x97GWG\xef\xbe\t>-\xcb\xdd\x0cw\xed\xd1;\xd2\xb5"
    },
    service_data={
        "0000feaa-0000-1000-8000-00805f9b34fb": b' \x00\x0c\x86\x80\x00\x00\x00\x93f\x0b\x7f\x93"',
        "0000fff0-0000-1000-8000-00805f9b34fb": b"'\x02\x17\x92\xdc\r0\x0e \xbad",
    },
    service_uuids=[
        "0000feaa-0000-1000-8000-00805f9b34fb",
        "0000fef5-0000-1000-8000-00805f9b34fb",
    ],
    source="local",
)


def bluetooth_service_info_replace(
    info: BluetoothServiceInfo, **kwargs: Any
) -> BluetoothServiceInfo:
    """Replace attributes of a BluetoothServiceInfoBleak."""
    return BluetoothServiceInfo(
        address=kwargs.get("address", info.address),
        name=kwargs.get("name", info.name),
        rssi=kwargs.get("rssi", info.rssi),
        manufacturer_data=kwargs.get("manufacturer_data", info.manufacturer_data),
        service_data=kwargs.get("service_data", info.service_data),
        service_uuids=kwargs.get("service_uuids", info.service_uuids),
        source=kwargs.get("source", info.source),
    )
