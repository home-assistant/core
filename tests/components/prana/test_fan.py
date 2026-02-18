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
    # The default mock state has bound=False.
    # Therefore, 'supply' and 'extract' fans will be available, while 'bounded' will be unavailable.
    # This expected availability state is captured by the snapshot.
    with patch("homeassistant.components.prana.PLATFORMS", [Platform.FAN]):
        await async_init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("type_key", "entity_suffix", "is_bound_mode"),
    [
        ("supply", "_supply", False),
        ("extract", "_extract", False),
        ("bounded", "_bounded", True),
    ],
)
async def test_fans_actions(
    hass: HomeAssistant,
    mock_prana_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    type_key: str,
    entity_suffix: str,
    is_bound_mode: bool,
) -> None:
    """Test turning fans on/off, setting speed and presets."""

    # Set the bound mode in the mock state.
    # This determines entity availability: 'bounded' is only available when bound=True.
    mock_prana_api.get_state.return_value.bound = is_bound_mode

    # Ensure the fan is initially ON in the mock.
    # Home Assistant optimizes service calls and will not send a 'turn_off' command
    # if it believes the entity is already off.
    getattr(mock_prana_api.get_state.return_value, type_key).is_on = True

    await async_init_integration(hass, mock_config_entry)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entries
    target = f"fan.prana_recuperator{entity_suffix}"

    # --- Test Turn OFF ---
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: target},
        blocking=True,
    )
    mock_prana_api.set_speed_is_on.assert_called_with(False, type_key)

    # Reset the mock to clear the previous call history.
    mock_prana_api.reset_mock()

    # --- Test Turn ON ---
    # Update the mock state to OFF.
    # Home Assistant requires the entity to be off to process a 'turn_on' command.
    getattr(mock_prana_api.get_state.return_value, type_key).is_on = False

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: target},
        blocking=True,
    )
    mock_prana_api.set_speed_is_on.assert_called_with(True, type_key)

    # --- Test Set Percentage (Speed) ---
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: target, ATTR_PERCENTAGE: 50},
        blocking=True,
    )

    # Verify the API was called and the correct type key (e.g., 'supply') was passed.
    mock_prana_api.set_speed.assert_called()
    assert mock_prana_api.set_speed.call_args[0][1] == type_key

    # --- Test Preset Mode ---
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: target, ATTR_PRESET_MODE: "night"},
        blocking=True,
    )
    mock_prana_api.set_switch.assert_called_with("night", True)
