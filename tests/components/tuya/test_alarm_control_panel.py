"""Test Tuya Alarm Control Panel platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    AlarmControlPanelState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
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


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.ALARM_CONTROL_PANEL])
@pytest.mark.parametrize(
    "mock_device_code",
    ["mal_gyitctrjj1kefxp2"],
)
@pytest.mark.parametrize(
    ("service", "command"),
    [
        (SERVICE_ALARM_ARM_AWAY, {"code": "master_mode", "value": "arm"}),
        (SERVICE_ALARM_ARM_HOME, {"code": "master_mode", "value": "home"}),
        (SERVICE_ALARM_DISARM, {"code": "master_mode", "value": "disarmed"}),
        (SERVICE_ALARM_TRIGGER, {"code": "master_mode", "value": "sos"}),
    ],
)
async def test_service(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    command: dict[str, Any],
) -> None:
    """Test service."""
    entity_id = "alarm_control_panel.multifunction_alarm"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        ALARM_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(mock_device.id, [command])


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.ALARM_CONTROL_PANEL])
@pytest.mark.parametrize(
    "mock_device_code",
    ["mal_gyitctrjj1kefxp2"],
)
@pytest.mark.parametrize(
    ("status_updates", "expected_state"),
    [
        (
            {"master_mode": "disarmed"},
            AlarmControlPanelState.DISARMED,
        ),
        (
            {"master_mode": "arm"},
            AlarmControlPanelState.ARMED_AWAY,
        ),
        (
            {"master_mode": "home"},
            AlarmControlPanelState.ARMED_HOME,
        ),
        (
            {"master_mode": "sos"},
            AlarmControlPanelState.TRIGGERED,
        ),
        (
            {
                "master_mode": "home",
                "master_state": "alarm",
                # "Test Sensor" in UTF-16BE
                "alarm_msg": "AFQAZQBzAHQAIABTAGUAbgBzAG8Acg==",
            },
            AlarmControlPanelState.TRIGGERED,
        ),
        (
            {
                "master_mode": "home",
                "master_state": "alarm",
                # "Sensor Low Battery Test Sensor" in UTF-16BE
                "alarm_msg": "AFMAZQBuAHMAbwByACAATABvAHcAIABCAGEAdAB0AGUAcgB5ACAAVABlAHMAdAAgAFMAZQBuAHMAbwBy",
            },
            AlarmControlPanelState.ARMED_HOME,
        ),
    ],
)
async def test_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    status_updates: dict[str, Any],
    expected_state: str,
) -> None:
    """Test state."""
    entity_id = "alarm_control_panel.multifunction_alarm"
    mock_device.status.update(status_updates)
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.state == expected_state
