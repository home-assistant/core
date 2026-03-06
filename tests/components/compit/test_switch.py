"""Tests for the Compit switch platform."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_compit_entities

from tests.common import MockConfigEntry


async def test_switch_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test for switch entities creation, unique IDs, and device info."""
    await setup_integration(hass, mock_config_entry)

    snapshot_compit_entities(hass, entity_registry, snapshot, Platform.SWITCH)


async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test turning a switch on."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: "switch.nano_color_2_holiday_mode"},  # Was off from conftest
        blocking=True,
    )

    mock_connector.select_device_option.assert_called_once()
    call_args = mock_connector.select_device_option.call_args[0]
    assert call_args[2] == STATE_ON

    state = hass.states.get("switch.nano_color_2_holiday_mode")
    assert state is not None
    assert state.state == STATE_ON


async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test turning a switch off."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {
            ATTR_ENTITY_ID: "switch.nano_color_2_out_of_home_mode"
        },  # Was on from conftest
        blocking=True,
    )
    mock_connector.select_device_option.assert_called_once()
    call_args = mock_connector.select_device_option.call_args[0]
    assert call_args[2] == STATE_OFF

    state = hass.states.get("switch.nano_color_2_out_of_home_mode")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "mock_return_value",
    [
        None,
        "invalid",
    ],
)
async def test_switch_unknown_device_parameters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    mock_return_value: Any,
) -> None:
    """Test that switch entity shows unknown when get_current_option returns various invalid values."""
    mock_connector.get_current_option.side_effect = lambda device_id, parameter_code: (
        mock_return_value
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.nano_color_2_holiday_mode")
    assert state is not None
    assert state.state == STATE_UNKNOWN
