"""Tests for the Aranet integration."""

from time import time

from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_ble_device


def fake_service_info(name, service_uuid, manufacturer_data):
    """Return a BluetoothServiceInfoBleak for use in testing."""
    return BluetoothServiceInfoBleak(
        name=name,
        address="aa:bb:cc:dd:ee:ff",
        rssi=-60,
        manufacturer_data=manufacturer_data,
        service_data={},
        service_uuids=[service_uuid],
        source="local",
        connectable=False,
        time=time(),
        device=generate_ble_device("aa:bb:cc:dd:ee:ff", name=name),
        advertisement=AdvertisementData(
            local_name=name,
            manufacturer_data=manufacturer_data,
            service_data={},
            service_uuids=[service_uuid],
            rssi=-60,
            tx_power=-127,
            platform_data=(),
        ),
        tx_power=-127,
    )


NOT_ARANET4_SERVICE_INFO = fake_service_info(
    "Not it", "61DE521B-F0BF-9F44-64D4-75BBE1738105", {3234: b"\x00\x01"}
)

OLD_FIRMWARE_SERVICE_INFO = fake_service_info(
    "Aranet4 12345",
    "f0cd1400-95da-4f4b-9ac8-aa55d312af0c",
    {1794: b"\x21\x0a\x04\x00\x00\x00\x00\x00"},
)

DISABLED_INTEGRATIONS_SERVICE_INFO = fake_service_info(
    "Aranet4 12345",
    "0000fce0-0000-1000-8000-00805f9b34fb",
    {1794: b"\x01\x00\x02\x01\x00\x00\x00\x00"},
)

VALID_DATA_SERVICE_INFO = fake_service_info(
    "Aranet4 12345",
    "0000fce0-0000-1000-8000-00805f9b34fb",
    {
        1794: b'\x21\x00\x02\x01\x00\x00\x00\x01\x8a\x02\xa5\x01\xb1&"Y\x01,\x01\xe8\x00\x88'
    },
)

VALID_DATA_SERVICE_INFO_WITH_NO_NAME = fake_service_info(
    None,
    "0000fce0-0000-1000-8000-00805f9b34fb",
    {
        1794: b'\x21\x00\x02\x01\x00\x00\x00\x01\x8a\x02\xa5\x01\xb1&"Y\x01,\x01\xe8\x00\x88'
    },
)

VALID_ARANET2_DATA_SERVICE_INFO = fake_service_info(
    "Aranet2 12345",
    "0000fce0-0000-1000-8000-00805f9b34fb",
    {
        1794: b"\x01!\x04\x04\x01\x00\x00\x00\x00\x00\xf0\x01\x00\x00\x0c\x02\x00O\x00<\x00\x01\x00\x80"
    },
)

VALID_ARANET_RADIATION_DATA_SERVICE_INFO = fake_service_info(
    "Aranet\u2622 12345",
    "0000fce0-0000-1000-8000-00805f9b34fb",
    {
        1794: b"\x02!&\x04\x01\x00`-\x00\x00\x08\x98\x05\x00n\x00\x00d\x00,\x01\xfd\x00\xc7"
    },
)
