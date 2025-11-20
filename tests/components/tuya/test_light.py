"""Test Tuya light platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_WHITE,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.LIGHT])
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
    ["dj_mki13ie507rlry4r"],
)
@pytest.mark.parametrize(
    ("service", "service_data", "expected_commands"),
    [
        (
            SERVICE_TURN_ON,
            {
                ATTR_WHITE: True,
            },
            [
                {"code": "switch_led", "value": True},
                {"code": "work_mode", "value": "white"},
                {"code": "bright_value_v2", "value": 546},
            ],
        ),
        (
            SERVICE_TURN_ON,
            {
                ATTR_BRIGHTNESS: 150,
            },
            [
                {"code": "switch_led", "value": True},
                {"code": "bright_value_v2", "value": 592},
            ],
        ),
        (
            SERVICE_TURN_ON,
            {
                ATTR_WHITE: True,
                ATTR_BRIGHTNESS: 150,
            },
            [
                {"code": "switch_led", "value": True},
                {"code": "work_mode", "value": "white"},
                {"code": "bright_value_v2", "value": 592},
            ],
        ),
        (
            SERVICE_TURN_ON,
            {
                ATTR_WHITE: 150,
            },
            [
                {"code": "switch_led", "value": True},
                {"code": "work_mode", "value": "white"},
                {"code": "bright_value_v2", "value": 592},
            ],
        ),
        (
            SERVICE_TURN_OFF,
            {},
            [{"code": "switch_led", "value": False}],
        ),
    ],
)
async def test_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    service_data: dict[str, Any],
    expected_commands: list[dict[str, Any]],
) -> None:
    """Test light action."""
    entity_id = "light.garage_light"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
            **service_data,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        expected_commands,
    )
