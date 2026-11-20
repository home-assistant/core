"""Test Tuya Alarm Control Panel platform."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelService,
    AlarmControlPanelState,
)
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import initialize_entry


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with patch(
        "homeassistant.components.tuya.PLATFORMS", [Platform.ALARM_CONTROL_PANEL]
    ):
        yield


@pytest.mark.usefixtures("no_quirk")
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
    ("mock_device_code", "entity_id"),
    [
        ("mal_gyitctrjj1kefxp2", "alarm_control_panel.multifunction_alarm"),
        ("wg2_pkhw2vbphv4csrir", "alarm_control_panel.c30"),
    ],
)
@pytest.mark.parametrize(
    ("service", "command"),
    [
        (AlarmControlPanelService.ARM_AWAY, {"code": "master_mode", "value": "arm"}),
        (AlarmControlPanelService.ARM_HOME, {"code": "master_mode", "value": "home"}),
        (AlarmControlPanelService.DISARM, {"code": "master_mode", "value": "disarmed"}),
        (AlarmControlPanelService.TRIGGER, {"code": "master_mode", "value": "sos"}),
    ],
)
async def test_service(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    command: dict[str, Any],
    entity_id: str,
) -> None:
    """Test service."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        ALARM_DOMAIN,
        service,
        {
            TargetKey.ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(mock_device.id, [command])


@pytest.mark.parametrize(
    ("mock_device_code", "entity_id"),
    [
        ("mal_gyitctrjj1kefxp2", "alarm_control_panel.multifunction_alarm"),
        ("wg2_pkhw2vbphv4csrir", "alarm_control_panel.c30"),
    ],
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
                "alarm_msg": (
                    "AFMAZQBuAHMAbwByACAATABvAHcAIABCAGEAdAB0"
                    "AGUAcgB5ACAAVABlAHMAdAAgAFMAZQBuAHMAbwBy"
                ),
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
    entity_id: str,
) -> None:
    """Test state."""
    mock_device.status.update(status_updates)
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.state == expected_state
