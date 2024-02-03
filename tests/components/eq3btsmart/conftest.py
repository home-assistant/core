"""Fixtures for eq3btsmart tests."""


from bleak.backends.scanner import AdvertisementData
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from .const import MAC, NAME, RSSI

from tests.components.bluetooth import generate_ble_device


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


@pytest.fixture
def fake_service_info():
    """Return a BluetoothServiceInfoBleak for use in testing."""
    return BluetoothServiceInfoBleak(
        name=NAME,
        address=MAC,
        rssi=RSSI,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        source="local",
        connectable=False,
        time=0,
        device=generate_ble_device(address=MAC, name=NAME, rssi=RSSI),
        advertisement=AdvertisementData(
            local_name=NAME,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            rssi=RSSI,
            tx_power=-127,
            platform_data=(),
        ),
    )
