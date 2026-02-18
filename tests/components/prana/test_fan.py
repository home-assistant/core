"""Integration-style tests for Prana fans."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_fans(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_prana_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Prana fans snapshot."""
    with patch("homeassistant.components.prana.PLATFORMS", [Platform.FAN]):
        await async_init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("type_key", "is_bound_mode"),
    [
        ("supply", False),
        ("extract", False),
        ("bounded", True),
    ],
)
async def test_fans_actions(
    hass: HomeAssistant,
    mock_prana_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    type_key: str,
    is_bound_mode: bool,
) -> None:
    """Test turning fans on/off, setting speed and presets."""
    # Set the mock API state for the fan type being tested
    mock_prana_api.get_state.return_value.bound = is_bound_mode

    await async_init_integration(hass, mock_config_entry)

    # Resolve the entity ID dynamically using the unique ID
    unique_id = f"{mock_config_entry.unique_id}_{type_key}"
    entity_entry = entity_registry.async_get_entity_id(FAN_DOMAIN, "prana", unique_id)

    assert entity_entry, f"Entity with unique_id {unique_id} not found in registry"
    target = entity_entry

    # --- Test Turn OFF ---
    # Force state to ON so HA allows turning off
    hass.states.async_set(target, "on")

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: target},
        blocking=True,
    )
    mock_prana_api.set_speed_is_on.assert_called_with(False, type_key)

    mock_prana_api.reset_mock()

    # --- Test Turn ON ---
    # Force state to OFF so HA allows turning on
    hass.states.async_set(target, "off")

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: target},
        blocking=True,
    )
    mock_prana_api.set_speed_is_on.assert_called_with(True, type_key)

    mock_prana_api.reset_mock()

    # --- Test Set Percentage (Speed 50%) ---
    hass.states.async_set(target, "on")

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: target, ATTR_PERCENTAGE: 50},
        blocking=True,
    )

    mock_prana_api.set_speed.assert_called()
    assert mock_prana_api.set_speed.call_args[0][1] == type_key

    mock_prana_api.reset_mock()

    # --- Test Set Percentage 0% (Should Turn OFF) ---
    # Ensure it is ON before we test turning it off via percentage
    hass.states.async_set(target, "on")

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: target, ATTR_PERCENTAGE: 0},
        blocking=True,
    )

    # Verify that setting 0% called the turn_off API method, not set_speed
    mock_prana_api.set_speed_is_on.assert_called_with(False, type_key)

    # --- Test Preset Mode ---
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: target, ATTR_PRESET_MODE: "night"},
        blocking=True,
    )
    mock_prana_api.set_switch.assert_called_with("night", True)
