"""Test Tuya light platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
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
    ("mock_device_code", "entity_id", "service", "service_data", "expected_commands"),
    [
        (
            "dj_mki13ie507rlry4r",
            "light.garage_light",
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
            "dj_mki13ie507rlry4r",
            "light.garage_light",
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
            "dj_mki13ie507rlry4r",
            "light.garage_light",
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
            "dj_mki13ie507rlry4r",
            "light.garage_light",
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
            "dj_mki13ie507rlry4r",
            "light.garage_light",
            SERVICE_TURN_ON,
            {
                ATTR_BRIGHTNESS: 255,
                ATTR_HS_COLOR: (10.1, 20.2),
            },
            [
                {"code": "switch_led", "value": True},
                {"code": "work_mode", "value": "colour"},
                {"code": "colour_data_v2", "value": '{"h": 10, "s": 202, "v": 1000}'},
            ],
        ),
        (
            "dj_mki13ie507rlry4r",
            "light.garage_light",
            SERVICE_TURN_OFF,
            {},
            [{"code": "switch_led", "value": False}],
        ),
        (
            "dj_ilddqqih3tucdk68",
            "light.ieskas",
            SERVICE_TURN_ON,
            {
                ATTR_BRIGHTNESS: 255,
                ATTR_COLOR_TEMP_KELVIN: 5000,
            },
            [
                {"code": "switch_led", "value": True},
                {"code": "temp_value", "value": 221},
                {"code": "bright_value", "value": 255},
            ],
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
    """Test light action."""
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
