"""Tests for the MikroTik BT5 integration."""

from time import time

from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_ble_device


def fake_service_info(manufacturer_data):
    """Return a BluetoothServiceInfoBleak for use in testing."""
    return BluetoothServiceInfoBleak(
        name="AA-BB-CC-DD-EE-FF",
        address="aa:bb:cc:dd:ee:ff",
        rssi=-60,
        manufacturer_data=manufacturer_data,
        service_data={},
        service_uuids=[],
        source="local",
        connectable=False,
        time=time(),
        device=generate_ble_device("aa:bb:cc:dd:ee:ff", name="AA-BB-CC-DD-EE-FF"),
        advertisement=AdvertisementData(
            local_name="AA-BB-CC-DD-EE-FF",
            manufacturer_data=manufacturer_data,
            service_data={},
            service_uuids=[],
            rssi=-60,
            tx_power=-127,
            platform_data=(),
        ),
        tx_power=-127,
    )


NOT_MT_DATA = fake_service_info(
    {8323: b'\x01\x00\xdbA\xff\xff\xff\xff\x02\x00\x80\x16\xe3\x1e\xda\x04\x00R'}
)

UNSUPPORTED_VERSION_DATA = fake_service_info(
    {2383: b'\x99\x00\xdbA\xff\xff\xff\xff\x02\x00\x80\x16\xe3\x1e\xda\x04\x00R'},
)

VALID_DATA = fake_service_info(
    {2383: b'\x01\x00\xdbA\xE0\xff\xaa\xff\x02\x00\x80\x16\xe3\x1e\xda\x04\x00R'},
)

VALID_NO_TEMPERATURE_DATA = fake_service_info(
    {2383: b'\x01\x00\xdbA\xE0\x00\x00\x01\x00\x00\x00\x80\xe3\x1e\xda\x04\x00\x64'},
)
