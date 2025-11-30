"""Test Tuya fan platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.FAN])
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


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.FAN])
@pytest.mark.parametrize(
    ("mock_device_code", "entity_id", "service", "service_data", "expected_commands"),
    [
        (
            "ks_j9fa8ahzac8uvlfl",
            "fan.tower_fan_ca_407g_smart",
            SERVICE_OSCILLATE,
            {"oscillating": False},
            [{"code": "switch_horizontal", "value": False}],
        ),
        (
            "ks_j9fa8ahzac8uvlfl",
            "fan.tower_fan_ca_407g_smart",
            SERVICE_OSCILLATE,
            {"oscillating": True},
            [{"code": "switch_horizontal", "value": True}],
        ),
        (
            "fs_g0ewlb1vmwqljzji",
            "fan.ceiling_fan_with_light",
            SERVICE_SET_DIRECTION,
            {"direction": "forward"},
            [{"code": "fan_direction", "value": "forward"}],
        ),
        (
            "ks_j9fa8ahzac8uvlfl",
            "fan.tower_fan_ca_407g_smart",
            SERVICE_SET_PRESET_MODE,
            {"preset_mode": "sleep"},
            [{"code": "mode", "value": "sleep"}],
        ),
        (
            "fs_g0ewlb1vmwqljzji",
            "fan.ceiling_fan_with_light",
            SERVICE_TURN_OFF,
            {},
            [{"code": "switch", "value": False}],
        ),
        (
            "fs_g0ewlb1vmwqljzji",
            "fan.ceiling_fan_with_light",
            SERVICE_TURN_ON,
            {"preset_mode": "sleep"},
            [{"code": "switch", "value": True}, {"code": "mode", "value": "sleep"}],
        ),
    ],
)
async def test_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_id: str,
    service: str,
    service_data: dict[str, Any],
    expected_commands: list[dict[str, Any]],
) -> None:
    """Test fan action."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
            **service_data,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, expected_commands
    )
