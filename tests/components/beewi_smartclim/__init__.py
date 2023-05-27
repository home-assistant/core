"""Tests for the BeeWi SmartClim integration."""

from time import time

from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_ble_device


def fake_service_info(name, manufacturer_data):
    """Return a BluetoothServiceInfoBleak for use in testing."""
    return BluetoothServiceInfoBleak(
        name=name,
        address="aa:bb:cc:dd:ee:ff",
        rssi=-60,
        manufacturer_data=manufacturer_data,
        service_data={},
        service_uuids=[],
        source="local",
        connectable=False,
        time=time(),
        device=generate_ble_device("aa:bb:cc:dd:ee:ff", name=name),
        advertisement=AdvertisementData(
            local_name=name,
            manufacturer_data=manufacturer_data,
            service_data={},
            service_uuids=[],
            rssi=-60,
            tx_power=-127,
            platform_data=(),
        ),
    )


SMART_CLIM_VALID = fake_service_info(
    name="089352809434933736",
    manufacturer_data={13: b"\x05\x00\x93\x00\x02V\x07\x00\x00\x06,"},
)


NOT_SMART_CLIM_DEVICE = fake_service_info(
    name="089352809434933736",
    manufacturer_data={13: b"\x06\x00\x93\x00\x02V\x07\x00\x00\x06,"},
)
