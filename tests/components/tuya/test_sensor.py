"""Test Tuya sensor platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import ManagerCompat
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import DEVICE_MOCKS, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "mock_device_code", [k for k, v in DEVICE_MOCKS.items() if Platform.SENSOR in v]
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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
    "mock_device_code", [k for k, v in DEVICE_MOCKS.items() if Platform.SENSOR not in v]
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
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


@pytest.mark.parametrize(
    ("mock_device_code", "expected_entity_id", "expected_value_key"),
    [
        ("cwwsq_cleverio_pf100", "sensor.cleverio_pf100_meal_plan", "meal_plan"),
        ("zndb_smart_meter", "sensor.meter_phase_a_power", "power"),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_selected_sensors_from_fixture(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    expected_entity_id: str,
    expected_value_key: str,
) -> None:
    """Test if sensor state is returned for devices with raw data."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(expected_entity_id)
    assert state is not None, f"{expected_entity_id} does not exist"
    expected_value = mock_device.status.get(expected_value_key)
    assert state.state == expected_value or state.state is not None, (
        f"{expected_entity_id}: {state.state} != {expected_value}"
    )
