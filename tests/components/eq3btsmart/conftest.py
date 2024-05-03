"""Fixtures for eq3btsmart tests."""

from bleak.backends.scanner import AdvertisementData
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from .const import MAC

from tests.components.bluetooth import generate_ble_device


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


@pytest.fixture
def fake_service_info():
    """Return a BluetoothServiceInfoBleak for use in testing."""
    return BluetoothServiceInfoBleak(
        name="CC-RT-BLE",
        address=MAC,
        rssi=0,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        source="local",
        connectable=False,
        time=0,
        device=generate_ble_device(address=MAC, name="CC-RT-BLE", rssi=0),
        advertisement=AdvertisementData(
            local_name="CC-RT-BLE",
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            rssi=0,
            tx_power=-127,
            platform_data=(),
        ),
        tx_power=-127,
    )
