"""Test fixtures for Mitsubishi Comfort integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from mitsubishi_comfort import DeviceInfo, DeviceStatus
import pytest

from homeassistant.components.mitsubishi_comfort.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_USERNAME = "test@test.com"
MOCK_PASSWORD = "testpass"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
        unique_id=DOMAIN,
    )


@pytest.fixture
def mock_device_info() -> DeviceInfo:
    """Return a mock DeviceInfo."""
    return DeviceInfo(
        serial="SERIAL001",
        label="Living Room",
        address="192.168.1.100",
        mac="AA:BB:CC:DD:EE:FF",
        unit_type="ductless",
        password="dGVzdHBhc3M=",
        crypto_serial="0102030405060708090a",
    )


@pytest.fixture
def mock_device_status() -> DeviceStatus:
    """Return a realistic DeviceStatus."""
    return DeviceStatus(
        mode="cool",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=45.0,
        outdoor_temperature=30.0,
        wifi_rssi=-55,
        sensor_battery=80,
        sensor_rssi=-60,
        run_state="on",
        vane_left_right="auto",
        uptime=86400,
        firmware_version="2.1.0",
        hardware_version="1.0.0",
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )


@pytest.fixture
def mock_cloud_account(mock_device_info: DeviceInfo) -> Generator[AsyncMock]:
    """Mock MitsubishiCloudAccount."""
    with patch(
        "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount"
    ) as mock_cls:
        account = AsyncMock()
        account.login = AsyncMock(return_value=True)
        account.discover_devices = AsyncMock(
            return_value={"SERIAL001": mock_device_info}
        )
        account.get_passwords_via_websocket = AsyncMock(return_value={})
        account.close = AsyncMock()
        mock_cls.return_value = account
        yield account
