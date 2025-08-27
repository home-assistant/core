"""Fixtures for Mammotion tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from bleak.backends.device import BLEDevice
from habluetooth.models import BluetoothServiceInfoBleak
import pytest

from homeassistant.components.mammotion.const import CONF_ACCOUNTNAME, DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

DEFAULT_NAME = "Luba-ABC123"
MAMMOTION_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Luba-ABC123",
    address="AA:BB:CC:DD:EE:FF",
    device=generate_ble_device(
        address="AA:BB:CC:DD:EE:FF",
        name="Luba-ABC123",
    ),
    rssi=-61,
    manufacturer_data={},
    service_data={},
    service_uuids=["0000ffff-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={},
        service_uuids=["0000ffff-0000-1000-8000-00805f9b34fb"],
    ),
    connectable=True,
    time=0,
    tx_power=None,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.mammotion.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(name="discovery")
def mock_async_discovered_service_info() -> Generator[MagicMock]:
    """Mock service discovery."""
    with patch(
        "homeassistant.components.mammotion.config_flow.async_discovered_service_info",
        return_value=[MAMMOTION_SERVICE_INFO],
    ) as discovery:
        yield discovery


@pytest.fixture(name="ble_device")
def mock_ble_device() -> Generator[MagicMock]:
    """Mock BLEDevice."""
    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=BLEDevice(
            address="AA:BB:CC:DD:EE:FF", name=DEFAULT_NAME, details={}
        ),
    ) as ble_device:
        yield ble_device


@pytest.fixture
def mock_cloud_gateway():
    """Mock a CloudIOTGateway."""
    mock_cloud = Mock()
    mock_cloud.mammotion_http = Mock()
    mock_cloud.mammotion_http.login_info = Mock()
    mock_cloud.mammotion_http.login_info.userInformation = Mock()
    mock_cloud.mammotion_http.login_info.userInformation.userAccount = "user123"
    return mock_cloud


@pytest.fixture
def mock_http_response():
    """Mock a successful HTTP login response."""
    mock_response = Mock()
    mock_response.login_info = Mock()
    mock_response.login_info.userInformation = Mock()
    mock_response.login_info.userInformation.userAccount = "user123"
    return mock_response


@pytest.fixture
def mock_mammotion():
    """Mock Mammotion class."""
    mock = AsyncMock()
    mock.mqtt_list = {}
    mock.login_and_initiate_cloud = AsyncMock()
    return mock


@pytest.fixture
def mock_config_entry():
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCOUNTNAME: "user@example.com",
            CONF_PASSWORD: "password",
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        },
        unique_id="user123",
    )


@pytest.fixture
def mock_mower_coordinator():
    """Return a mocked mower coordinator."""
    coordinator = AsyncMock()
    coordinator.data = Mock()
    coordinator.data.report_data = Mock()
    coordinator.data.report_data.dev = Mock()
    return coordinator
