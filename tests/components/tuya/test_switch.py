"""Test Tuya switch platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockDeviceListener, check_selective_state_update, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SWITCH])
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
    ["cz_PGEkBctAbtzKOZng"],
)
@pytest.mark.parametrize(
    ("updates", "expected_state", "last_reported"),
    [
        # Update without dpcode - state should not change, last_reported stays
        # at available_reported
        ({"countdown_1": 50}, "off", "2024-01-01T00:00:20+00:00"),
        # Update with dpcode - state should change, last_reported advances
        ({"switch": True}, "on", "2024-01-01T00:01:00+00:00"),
        # Update with multiple properties including dpcode - state should change
        (
            {"countdown_1": 50, "switch": True},
            "on",
            "2024-01-01T00:01:00+00:00",
        ),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SWITCH])
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
        entity_id="switch.din_socket",
        dpcode="switch",
        initial_state="off",
        updates=updates,
        expected_state=expected_state,
        last_reported=last_reported,
    )


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SWITCH])
@pytest.mark.parametrize(
    "mock_device_code",
    ["cz_PGEkBctAbtzKOZng"],
)
@pytest.mark.parametrize(
    ("service", "expected_commands"),
    [
        (
            SERVICE_TURN_ON,
            [{"code": "switch", "value": True}],
        ),
        (
            SERVICE_TURN_OFF,
            [{"code": "switch", "value": False}],
        ),
    ],
)
async def test_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    expected_commands: list[dict[str, Any]],
) -> None:
    """Test switch action."""
    entity_id = "switch.din_socket"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, expected_commands
    )


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.SWITCH])
@pytest.mark.parametrize(
    "mock_device_code",
    ["cz_PGEkBctAbtzKOZng"],
)
@pytest.mark.parametrize(
    ("initial_status", "expected_state"),
    [
        (True, "on"),
        (False, "off"),
        (None, STATE_UNKNOWN),
        ("some string", STATE_UNKNOWN),
    ],
)
async def test_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    initial_status: Any,
    expected_state: str,
) -> None:
    """Test switch state."""
    entity_id = "switch.din_socket"
    mock_device.status["switch"] = initial_status
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.state == expected_state
