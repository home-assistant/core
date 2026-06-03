"""Test fixtures for Mitsubishi Comfort integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from mitsubishi_comfort import (
    CommandResult,
    DeviceInfo,
    DeviceStatus,
    FanSpeed,
    IndoorUnit,
    Mode,
    VaneDirection,
)
import pytest

from homeassistant.components.mitsubishi_comfort.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_USERNAME = "test@test.com"
MOCK_PASSWORD = "testpass"


def _make_device_status(
    mode: str | None = "cool",
    standby: bool = False,
    vane_left_right: str | None = "auto",
    current_humidity: float | None = 45.0,
    min_cool_setpoint: float | None = 18.0,
    max_cool_setpoint: float | None = 30.0,
    min_heat_setpoint: float | None = 16.0,
    max_heat_setpoint: float | None = 28.0,
) -> DeviceStatus:
    """Create a DeviceStatus with sensible defaults."""
    return DeviceStatus(
        mode=mode,
        standby=standby,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=current_humidity,
        outdoor_temperature=30.0,
        wifi_rssi=-55,
        sensor_battery=80,
        sensor_rssi=-60,
        run_state="on",
        vane_left_right=vane_left_right,
        uptime=86400,
        firmware_version="2.1.0",
        hardware_version="1.0.0",
        min_cool_setpoint=min_cool_setpoint,
        max_cool_setpoint=max_cool_setpoint,
        min_heat_setpoint=min_heat_setpoint,
        max_heat_setpoint=max_heat_setpoint,
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
        unique_id="user-12345",
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
    return _make_device_status()


def create_mock_indoor_unit() -> MagicMock:
    """Create a mock IndoorUnit with realistic attributes."""
    device = MagicMock(spec=IndoorUnit)
    device.serial = "SERIAL001"
    device.name = "Living Room"
    device.status = _make_device_status()
    device.update_status = AsyncMock(return_value=True)
    device.close = AsyncMock()
    device.supported_modes = [
        Mode.OFF,
        Mode.COOL,
        Mode.HEAT,
        Mode.DRY,
        Mode.FAN,
        Mode.AUTO,
    ]
    device.supported_fan_speeds = [FanSpeed.QUIET, FanSpeed.LOW, FanSpeed.AUTO]
    device.supported_vane_directions = [
        VaneDirection.HORIZONTAL,
        VaneDirection.AUTO,
        VaneDirection.SWING,
    ]
    device.set_mode = AsyncMock(return_value=CommandResult(success=True, value="cool"))
    device.set_cool_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=24.0)
    )
    device.set_heat_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=21.0)
    )
    device.set_fan_speed = AsyncMock(
        return_value=CommandResult(success=True, value="auto")
    )
    device.set_vane_direction = AsyncMock(
        return_value=CommandResult(success=True, value="auto")
    )
    return device


@pytest.fixture
def mock_indoor_unit() -> MagicMock:
    """Return a mock IndoorUnit."""
    return create_mock_indoor_unit()


@pytest.fixture
def mock_cloud_account(mock_device_info: DeviceInfo) -> Generator[AsyncMock]:
    """Mock MitsubishiCloudAccount for both main code and config flow."""
    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
            autospec=True,
        ) as mock_cls,
        patch(
            "homeassistant.components.mitsubishi_comfort.config_flow.MitsubishiCloudAccount",
            new=mock_cls,
        ),
    ):
        account = mock_cls.return_value
        account.login.return_value = None
        account.discover_devices.return_value = {"SERIAL001": mock_device_info}
        account.get_passwords_via_websocket.return_value = {}
        account.user_id = "user-12345"
        yield account


@pytest.fixture
def mock_setup_integration(
    mock_cloud_account: AsyncMock,
    mock_indoor_unit: MagicMock,
) -> Generator[tuple[AsyncMock, MagicMock]]:
    """Patch IndoorUnit and KumoStation for full integration setup tests."""
    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.IndoorUnit",
            return_value=mock_indoor_unit,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.KumoStation",
            return_value=mock_indoor_unit,
        ),
    ):
        yield mock_cloud_account, mock_indoor_unit
