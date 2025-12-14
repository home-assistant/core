"""Test Tuya vacuum platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.VACUUM])
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
    ("mock_device_code", "entity_id", "service", "service_data", "expected_command"),
    [
        (
            "sd_i6hyjg3af7doaswm",
            "vacuum.hoover",
            SERVICE_RETURN_TO_BASE,
            {},
            {"code": "mode", "value": "chargego"},
        ),
        (
            # Based on #141278
            "sd_lr33znaodtyarrrz",
            "vacuum.v20",
            SERVICE_RETURN_TO_BASE,
            {},
            {"code": "switch_charge", "value": True},
        ),
        (
            "sd_lr33znaodtyarrrz",
            "vacuum.v20",
            SERVICE_SET_FAN_SPEED,
            {ATTR_FAN_SPEED: "gentle"},
            {"code": "suction", "value": "gentle"},
        ),
        (
            "sd_i6hyjg3af7doaswm",
            "vacuum.hoover",
            SERVICE_LOCATE,
            {},
            {"code": "seek", "value": True},
        ),
        (
            "sd_i6hyjg3af7doaswm",
            "vacuum.hoover",
            SERVICE_START,
            {},
            {"code": "power_go", "value": True},
        ),
        (
            "sd_i6hyjg3af7doaswm",
            "vacuum.hoover",
            SERVICE_STOP,
            {},
            {"code": "power_go", "value": False},
        ),
        (
            "sd_lr33znaodtyarrrz",
            "vacuum.v20",
            SERVICE_PAUSE,
            {},
            {"code": "power_go", "value": False},
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
    expected_command: dict[str, Any],
) -> None:
    """Test vacuum action."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        VACUUM_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
            **service_data,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [expected_command]
    )
