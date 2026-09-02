"""Fixtures for Marstek tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from aiomarstek import MarstekDeviceInfo, MarstekDeviceStatus, MarstekUDPClient
import pytest

from homeassistant.components.marstek.const import DOMAIN

from tests.common import MockConfigEntry

TEST_HOST = "192.168.1.100"
TEST_MAC = "AA:BB:CC:DD:EE:FF"
TEST_DEVICE_TYPE = "VenusE 3.0"
TEST_VERSION = 1
TEST_WIFI_NAME = "TestWiFi"
TEST_WIFI_MAC = "AA:BB:CC:DD:EE:FF"
TEST_BLE_MAC = "11:22:33:44:55:66"

MOCK_DEVICE_INFO = MarstekDeviceInfo(
    id=0,
    device_type=TEST_DEVICE_TYPE,
    version=TEST_VERSION,
    wifi_name=TEST_WIFI_NAME,
    ip=TEST_HOST,
    wifi_mac=TEST_WIFI_MAC,
    ble_mac=TEST_BLE_MAC,
    mac=TEST_MAC,
)

MOCK_DISCOVERY_RESPONSE = {
    "id": 1,
    "result": MOCK_DEVICE_INFO,
}

MOCK_DEVICE_STATUS = MarstekDeviceStatus(
    device_ip=TEST_HOST,
    battery_soc=85,
    battery_power=1300,
    device_mode="manual",
    battery_status="charging",
    pv1_power=500,
    pv1_voltage=48,
    pv1_current=10,
    pv1_state="working",
)


@pytest.fixture(autouse=True)
def mock_udp_client() -> Generator[MagicMock]:
    """Mock the Marstek UDP client factory."""
    mock_client = create_autospec(MarstekUDPClient, instance=True)
    mock_client.send_request.return_value = {"id": 1, "result": {}}
    mock_client.send_broadcast_request.return_value = []
    mock_client.discover_devices.return_value = []
    mock_client.get_device_info.return_value = MOCK_DEVICE_INFO
    mock_client.get_device_status.return_value = MOCK_DEVICE_STATUS
    mock_client.get_discovery_cache.return_value = None
    mock_client.is_polling_paused.return_value = False
    with (
        patch(
            "homeassistant.components.marstek.async_create_udp_client",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.marstek.config_flow.async_create_udp_client",
            return_value=mock_client,
        ),
    ):
        yield mock_client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.marstek.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a Marstek config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"{TEST_DEVICE_TYPE} v{TEST_VERSION} ({TEST_HOST})",
        unique_id=TEST_MAC,
        data={
            "host": TEST_HOST,
            "mac": TEST_MAC,
            "device_type": TEST_DEVICE_TYPE,
            "version": TEST_VERSION,
            "wifi_name": TEST_WIFI_NAME,
            "wifi_mac": TEST_WIFI_MAC,
            "ble_mac": TEST_BLE_MAC,
        },
    )
