"""Test Tuya climate platform."""

from __future__ import annotations

from typing import cast
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.climate import HVACMode
from homeassistant.components.tuya import ManagerCompat
from homeassistant.components.tuya.climate import (
    TuyaClimateEntity,
    TuyaClimateEntityDescription,
)
from homeassistant.components.tuya.const import DPCode
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import DEVICE_MOCKS, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


class DummyDevice:
    """Dummy device for testing."""

    def __init__(self, function, status) -> None:
        """Initialize the dummy device."""
        self.function = function
        self.status = status
        self.id = "dummy"
        self.name = "Dummy"
        self.product_name = "Dummy"
        self.product_id = "dummy"
        self.status_range = {}
        self.online = True


class DummyManager:
    """Dummy manager for testing."""

    def send_commands(self, device_id: str, commands: list) -> None:
        """Send commands to the device."""


class DummyFunction:
    """Dummy function for testing."""

    def __init__(self, type_: str, values: str) -> None:
        """Initialize the dummy function."""
        self.type = type_
        self.values = values


def make_climate_entity(function, status):
    """Make a dummy climate entity for testing."""
    return TuyaClimateEntity(
        cast("CustomerDevice", DummyDevice(function, status)),
        cast("Manager", DummyManager()),
        TuyaClimateEntityDescription(key="kt", switch_only_hvac_mode=HVACMode.COOL),
        UnitOfTemperature.CELSIUS,
    )


@pytest.mark.parametrize(
    "mock_device_code",
    [k for k, v in DEVICE_MOCKS.items() if Platform.CLIMATE in v],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.CLIMATE])
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_device_code",
    [k for k, v in DEVICE_MOCKS.items() if Platform.CLIMATE not in v],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.CLIMATE])
async def test_platform_setup_no_discovery(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test platform setup without discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


def test_fan_mode_windspeed() -> None:
    """Test fan mode with windspeed."""
    entity = make_climate_entity(
        {"windspeed": DummyFunction("Enum", '{"range": ["1", "2"]}')},
        {"windspeed": "2"},
    )
    assert entity.fan_mode == "2"
    entity.set_fan_mode("1")


def test_fan_mode_fan_speed_enum() -> None:
    """Test fan mode with fan speed enum."""
    entity = make_climate_entity(
        {DPCode.FAN_SPEED_ENUM: DummyFunction("Enum", '{"range": ["1", "2"]}')},
        {DPCode.FAN_SPEED_ENUM: "1"},
    )
    assert entity.fan_mode == "1"
    entity.set_fan_mode("2")


def test_fan_mode_no_valid_code() -> None:
    """Test fan mode with no valid code."""
    entity = make_climate_entity({}, {})
    assert entity.fan_mode is None
    with pytest.raises(HomeAssistantError):
        entity.set_fan_mode("1")
