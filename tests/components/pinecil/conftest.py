"""Fixtures for Pinecil tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from habluetooth import BluetoothServiceInfoBleak
from pynecil import DeviceInfoResponse, LiveDataResponse, OperatingMode, PowerSource
import pytest

from homeassistant.components.pinecil import DOMAIN
from homeassistant.const import CONF_ADDRESS

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

USER_INPUT = {CONF_ADDRESS: "c0:ff:ee:c0:ff:ee"}
DEFAULT_NAME = "Pinecil-C0FFEEE"
PINECIL_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Pinecil-C0FFEEE",
    address="c0:ff:ee:c0:ff:ee",
    device=generate_ble_device(
        address="c0:ff:ee:c0:ff:ee",
        name="Pinecil-C0FFEEE",
    ),
    rssi=-61,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={},
        service_uuids=["9eae1000-9d0d-48c5-aa55-33e27f9bc533"],
    ),
    connectable=True,
    time=0,
    tx_power=None,
)

UNKNOWN_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="",
    address="c0:ff:ee:c0:ff:ee",
    device=generate_ble_device(
        address="c0:ff:ee:c0:ff:ee",
        name="",
    ),
    rssi=-61,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={},
        service_uuids=[],
    ),
    connectable=True,
    time=0,
    tx_power=None,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pinecil.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="discovery")
def mock_async_discovered_service_info() -> Generator[MagicMock]:
    """Mock service discovery."""
    with patch(
        "homeassistant.components.pinecil.config_flow.async_discovered_service_info",
        return_value=[PINECIL_SERVICE_INFO, UNKNOWN_SERVICE_INFO],
    ) as discovery:
        yield discovery


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Pinecil configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={},
        unique_id="c0:ff:ee:c0:ff:ee",
        entry_id="1234567890",
    )


@pytest.fixture(name="ble_device")
def mock_ble_device() -> Generator[MagicMock]:
    """Mock BLEDevice."""
    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=BLEDevice(
            address="c0:ff:ee:c0:ff:ee", name=DEFAULT_NAME, rssi=-50, details={}
        ),
    ) as ble_device:
        yield ble_device


@pytest.fixture
def mock_pynecil() -> Generator[AsyncMock, None, None]:
    """Mock Pynecil library."""
    with patch(
        "homeassistant.components.pinecil.Pynecil", autospec=True
    ) as mock_client:
        client = mock_client.return_value

        client.get_device_info.return_value = DeviceInfoResponse(
            build="v2.22",
            device_id="c0ffeeC0",
            address="c0:ff:ee:c0:ff:ee",
            device_sn="0000c0ffeec0ffee",
            name=DEFAULT_NAME,
        )
        client.get_live_data.return_value = LiveDataResponse(
            live_temp=298,
            set_temp=300,
            dc_input=20.6,
            handle_temp=36.3,
            power_level=41,
            power_src=PowerSource.PD,
            tip_res=6.2,
            uptime=1671,
            movement=10000,
            max_temp=460,
            raw_tip=2212,
            hall_sensor=0,
            op_mode=OperatingMode.SOLDERING,
            est_power=24.8,
        )
        yield client
