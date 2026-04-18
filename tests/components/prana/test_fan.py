"""Integration-style tests for Prana fans."""

import math
from typing import Any
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

FAN_TEST_CASES = [
    ("supply", False, "supply"),
    ("extract", False, "extract"),
    ("supply", True, "bounded"),
    ("extract", True, "bounded"),
]


async def _async_setup_fan_entity(
    hass: HomeAssistant,
    mock_prana_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    type_key: str,
    is_bound_mode: bool,
) -> tuple[str, Any]:
    """Set up a Prana fan entity for service tests."""
    mock_prana_api.get_state.return_value.bound = is_bound_mode
    fan_mock_state = getattr(
        mock_prana_api.get_state.return_value,
        "bounded" if is_bound_mode else type_key,
    )

    await async_init_integration(hass, mock_config_entry)

    unique_id = f"{mock_config_entry.unique_id}_{type_key}"
    target = entity_registry.async_get_entity_id(FAN_DOMAIN, "prana", unique_id)

    assert target, f"Entity with unique_id {unique_id} not found"

    return target, fan_mock_state


async def test_fans(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_prana_api: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Prana fans snapshot."""
    with patch("homeassistant.components.prana.PLATFORMS", [Platform.FAN]):
        await async_init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("type_key", "is_bound_mode", "expected_api_key"),
    FAN_TEST_CASES,
)
async def test_fans_turn_on_off(
    hass: HomeAssistant,
    mock_prana_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    type_key: str,
    is_bound_mode: bool,
    expected_api_key: str,
) -> None:
    """Test turning Prana fans on and off."""
    target, fan_mock_state = await _async_setup_fan_entity(
        hass,
        mock_prana_api,
        mock_config_entry,
        entity_registry,
        type_key,
        is_bound_mode,
    )

    fan_mock_state.is_on = True
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: target},
        blocking=True,
    )
    mock_prana_api.set_speed_is_on.assert_called_with(False, expected_api_key)
    mock_prana_api.reset_mock()

    fan_mock_state.is_on = False
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: target},
        blocking=True,
    )
    mock_prana_api.set_speed_is_on.assert_called_with(True, expected_api_key)


@pytest.mark.parametrize(
    ("type_key", "is_bound_mode", "expected_api_key"),
    FAN_TEST_CASES,
)
async def test_fans_set_percentage(
    hass: HomeAssistant,
    mock_prana_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    type_key: str,
    is_bound_mode: bool,
    expected_api_key: str,
) -> None:
    """Test setting the Prana fan percentage."""
    target, fan_mock_state = await _async_setup_fan_entity(
        hass,
        mock_prana_api,
        mock_config_entry,
        entity_registry,
        type_key,
        is_bound_mode,
    )

    fan_mock_state.is_on = True
    await hass.async_block_till_done()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: target, ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    expected_speed = (
        math.ceil(percentage_to_ranged_value((1, fan_mock_state.max_speed), 50))
        * PRANA_SPEED_MULTIPLIER
    )
    mock_prana_api.set_speed.assert_called_once_with(
        expected_speed,
        expected_api_key,
    )
    mock_prana_api.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: target, ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    mock_prana_api.set_speed_is_on.assert_called_with(False, expected_api_key)


@pytest.mark.parametrize(
    ("type_key", "is_bound_mode", "expected_api_key"),
    FAN_TEST_CASES,
)
async def test_fans_set_preset_mode(
    hass: HomeAssistant,
    mock_prana_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    type_key: str,
    is_bound_mode: bool,
    expected_api_key: str,
) -> None:
    """Test setting the Prana fan preset mode."""
    target, _ = await _async_setup_fan_entity(
        hass,
        mock_prana_api,
        mock_config_entry,
        entity_registry,
        type_key,
        is_bound_mode,
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: target, ATTR_PRESET_MODE: "night"},
        blocking=True,
    )
    mock_prana_api.set_switch.assert_called_with("night", True)
