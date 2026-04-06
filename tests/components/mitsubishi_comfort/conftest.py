"""Test fixtures for Mitsubishi Comfort integration."""

from __future__ import annotations

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
    """Mock MitsubishiCloudAccount for config_flow tests."""
    with patch(
        "homeassistant.components.mitsubishi_comfort.config_flow.MitsubishiCloudAccount"
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


@pytest.fixture
def mock_setup_integration(
    mock_device_info: DeviceInfo,
    mock_indoor_unit: MagicMock,
) -> Generator[tuple[AsyncMock, MagicMock]]:
    """Patch cloud account and IndoorUnit for full integration setup tests.

    This patches at the __init__ module level so that async_setup_entry,
    the coordinator, climate platform, and entity code all run for real.
    """
    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=True)
    mock_account.discover_devices = AsyncMock(
        return_value={"SERIAL001": mock_device_info}
    )
    mock_account.get_passwords_via_websocket = AsyncMock(return_value={})
    mock_account.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.load_json",
            return_value={},
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.save_json",
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.IndoorUnit",
            return_value=mock_indoor_unit,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.KumoStation",
            return_value=mock_indoor_unit,
        ),
    ):
        yield mock_account, mock_indoor_unit
