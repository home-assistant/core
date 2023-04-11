"""Test updating sensors in the victron_ble integration."""
import pytest

from homeassistant.components.victron_ble import VictronBluetoothDeviceData

from .fixtures import (
    VICTRON_BATTERY_MONITOR_SERVICE_INFO,
    VICTRON_BATTERY_MONITOR_TOKEN,
    VICTRON_BATTERY_SENSE_SERVICE_INFO,
    VICTRON_BATTERY_SENSE_TOKEN,
    VICTRON_SOLAR_CHARGER_SERVICE_INFO,
    VICTRON_SOLAR_CHARGER_TOKEN,
    VICTRON_VEBUS_SERVICE_INFO,
    VICTRON_VEBUS_TOKEN,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Mock bluetooth for all tests in this module."""


async def test_async_update_battery_monitor() -> None:
    """Test updating sensors for a battery monitor."""
    device = VictronBluetoothDeviceData(VICTRON_BATTERY_MONITOR_TOKEN)
    device._start_update(VICTRON_BATTERY_MONITOR_SERVICE_INFO)


async def test_async_update_battery_sense() -> None:
    """Test updating sensors for a battery sense."""
    device = VictronBluetoothDeviceData(VICTRON_BATTERY_SENSE_TOKEN)
    device._start_update(VICTRON_BATTERY_SENSE_SERVICE_INFO)


async def test_async_update_solar_charger() -> None:
    """Test updating sensors for a solar charger."""
    device = VictronBluetoothDeviceData(VICTRON_SOLAR_CHARGER_TOKEN)
    device._start_update(VICTRON_SOLAR_CHARGER_SERVICE_INFO)


async def test_async_update_vebus() -> None:
    """Test updating sensors for a vebus device."""
    device = VictronBluetoothDeviceData(VICTRON_VEBUS_TOKEN)
    device._start_update(VICTRON_VEBUS_SERVICE_INFO)
