"""Fixtures for eq3btsmart tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from bleak.backends.scanner import AdvertisementData
from eq3btsmart.const import Eq3OperationMode
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from .const import MAC

from tests.components.bluetooth import generate_ble_device


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
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
        device=generate_ble_device(address=MAC, name="CC-RT-BLE"),
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


@pytest.fixture
def mock_thermostat() -> Generator[MagicMock]:
    """Return a mocked eQ-3 thermostat."""
    with patch(
        "homeassistant.components.eq3btsmart.Thermostat", autospec=True
    ) as thermostat_class:
        thermostat = thermostat_class.return_value
        thermostat.status = MagicMock(
            target_temperature=20.0,
            operation_mode=Eq3OperationMode.MANUAL,
            is_window_open=False,
            is_boost=False,
            is_low_battery=False,
            is_away=False,
            presets=None,
            valve=0,
        )
        yield thermostat
