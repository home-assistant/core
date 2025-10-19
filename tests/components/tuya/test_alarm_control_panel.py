"""Test Tuya Alarm Control Panel platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.ALARM_CONTROL_PANEL])
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
    ["mal_gyitctrjj1kefxp2"],
)
async def test_alarm_state_triggered(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test alarm state returns TRIGGERED for non-battery alarms."""
    entity_id = "alarm_control_panel.multifunction_alarm"

    # Set up alarm state without battery warning
    mock_device.status["master_state"] = "alarm"
    mock_device.status["alarm_msg"] = (
        "AFQAZQBzAHQAIABTAGUAbgBzAG8Acg=="  # "Test Sensor" in UTF-16BE
    )

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.state == AlarmControlPanelState.TRIGGERED


@pytest.mark.parametrize(
    "mock_device_code",
    ["mal_gyitctrjj1kefxp2"],
)
async def test_alarm_state_battery_warning(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test alarm state ignores battery warnings."""
    entity_id = "alarm_control_panel.multifunction_alarm"

    # Set up alarm state with battery warning
    mock_device.status["master_state"] = "alarm"
    mock_device.status["alarm_msg"] = (
        "AFMAZQBuAHMAbwByACAATABvAHcAIABCAGEAdAB0AGUAcgB5ACAAVABlAHMAdAAgAFMAZQBuAHMAbwBy"  # "Sensor Low Battery Test Sensor" in UTF-16BE
    )

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    # Should not be triggered for battery warnings
    assert state.state != AlarmControlPanelState.TRIGGERED
