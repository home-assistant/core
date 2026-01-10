"""Test Tuya sensor platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockDeviceListener, check_selective_state_update, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_device_code",
    ["mcs_8yhypbo7"],
)
@pytest.mark.parametrize(
    ("updates", "expected_state", "last_reported"),
    [
        # Update without dpcode - state should not change, last_reported stays at initial
        ({"doorcontact_state": True}, "62.0", "2024-01-01T00:00:00+00:00"),
        # Update with dpcode - state should change, last_reported advances
        ({"battery_percentage": 50}, "50.0", "2024-01-01T00:01:00+00:00"),
        # Update with multiple properties including dpcode - state should change
        (
            {"doorcontact_state": True, "battery_percentage": 50},
            "50.0",
            "2024-01-01T00:01:00+00:00",
        ),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR])
@pytest.mark.freeze_time("2024-01-01")
async def test_selective_state_update(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
    freezer: FrozenDateTimeFactory,
    updates: dict[str, Any],
    expected_state: str,
    last_reported: str,
) -> None:
    """Test skip_update/last_reported."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await check_selective_state_update(
        hass,
        mock_device,
        mock_listener,
        freezer,
        entity_id="sensor.boite_aux_lettres_arriere_battery",
        dpcode="battery_percentage",
        initial_state="62.0",
        updates=updates,
        expected_state=expected_state,
        last_reported=last_reported,
    )
