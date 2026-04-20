"""Integration-style tests for Prana fans."""

import math
from unittest.mock import AsyncMock, MagicMock, patch

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
from homeassistant.components.prana.fan import PRANA_SPEED_MULTIPLIER
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.percentage import percentage_to_ranged_value

from . import async_init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_fans(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_prana_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Prana fans snapshot (linked model, default fixture)."""
    with patch("homeassistant.components.prana.PLATFORMS", [Platform.FAN]):
        await async_init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_fans_split_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_prana_api: MagicMock,
) -> None:
    """Split models expose independent supply and extract fan entities."""
    mock_prana_api.get_state.return_value.bound = False

    with patch("homeassistant.components.prana.PLATFORMS", [Platform.FAN]):
        await async_init_integration(hass, mock_config_entry)

    unique_ids = {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert f"{mock_config_entry.unique_id}_supply" in unique_ids
    assert f"{mock_config_entry.unique_id}_extract" in unique_ids
    assert f"{mock_config_entry.unique_id}_ventilation" not in unique_ids


@pytest.mark.parametrize(
    ("entity_id", "api_target"),
    [
        ("fan.prana_recuperator_supply_fan", "supply"),
        ("fan.prana_recuperator_extract_fan", "extract"),
    ],
)
async def test_fans_split_api_targets(
    hass: HomeAssistant,
    mock_prana_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    api_target: str,
) -> None:
    """Split-mode fan entities address their own side of the device."""
    mock_prana_api.get_state.return_value.bound = False
    await async_init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_prana_api.set_speed_is_on.assert_called_with(False, api_target)

    mock_prana_api.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    mock_prana_api.set_speed.assert_called_once()
    assert mock_prana_api.set_speed.call_args.args[1] == api_target


async def test_fan_turn_on_off(
    hass: HomeAssistant,
    mock_prana_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Turning the ventilation fan on/off hits the bounded API target."""
    await async_init_integration(hass, mock_config_entry)

    target = "fan.prana_recuperator"

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: target},
        blocking=True,
    )
    mock_prana_api.set_speed_is_on.assert_called_with(False, "bounded")

    mock_prana_api.reset_mock()
    mock_prana_api.get_state.return_value.bounded.is_on = False
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: target},
        blocking=True,
    )
    mock_prana_api.set_speed_is_on.assert_called_with(True, "bounded")


async def test_fan_set_percentage(
    hass: HomeAssistant,
    mock_prana_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setting percentage calls set_speed with scaled value against bounded target."""
    await async_init_integration(hass, mock_config_entry)
    target = "fan.prana_recuperator"
    max_speed = mock_prana_api.get_state.return_value.bounded.max_speed

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: target, ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    expected_speed = (
        math.ceil(percentage_to_ranged_value((1, max_speed), 50))
        * PRANA_SPEED_MULTIPLIER
    )
    mock_prana_api.set_speed.assert_called_once_with(expected_speed, "bounded")

    mock_prana_api.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: target, ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    mock_prana_api.set_speed_is_on.assert_called_with(False, "bounded")


@pytest.mark.parametrize("preset_mode", ["auto", "auto_plus", "night", "boost"])
async def test_fan_set_preset_mode(
    hass: HomeAssistant,
    mock_prana_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    preset_mode: str,
) -> None:
    """Each preset mode maps to its device-side switch."""
    await async_init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "fan.prana_recuperator", ATTR_PRESET_MODE: preset_mode},
        blocking=True,
    )
    mock_prana_api.set_switch.assert_called_with(preset_mode, True)
