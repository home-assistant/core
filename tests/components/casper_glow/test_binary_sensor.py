"""Test the Casper Glow binary sensor platform."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, patch

from pycasperglow import GlowState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

PAUSED_ENTITY_ID = "binary_sensor.jar_dimming_paused"
CHARGING_ENTITY_ID = "binary_sensor.jar_charging"


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all binary sensor entities match the snapshot."""
    with patch(
        "homeassistant.components.casper_glow.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("is_paused", "expected_state"),
    [(True, STATE_ON), (False, STATE_OFF)],
    ids=["paused", "not-paused"],
)
async def test_paused_state_update(
    hass: HomeAssistant,
    mock_casper_glow: MagicMock,
    mock_config_entry: MockConfigEntry,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
    is_paused: bool,
    expected_state: str,
) -> None:
    """Test that the paused binary sensor reflects is_paused state changes."""
    with patch(
        "homeassistant.components.casper_glow.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await fire_callbacks(GlowState(is_paused=is_paused))
    state = hass.states.get(PAUSED_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_paused_ignores_none_state(
    hass: HomeAssistant,
    mock_casper_glow: MagicMock,
    mock_config_entry: MockConfigEntry,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test that a callback with is_paused=None does not overwrite the state."""
    with patch(
        "homeassistant.components.casper_glow.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    # Set a known value first
    await fire_callbacks(GlowState(is_paused=True))
    state = hass.states.get(PAUSED_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # Callback with no is_paused data — state should remain unchanged
    await fire_callbacks(GlowState(is_on=True))
    state = hass.states.get(PAUSED_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("is_charging", "expected_state"),
    [(True, STATE_ON), (False, STATE_OFF)],
    ids=["charging", "not-charging"],
)
async def test_charging_state_update(
    hass: HomeAssistant,
    mock_casper_glow: MagicMock,
    mock_config_entry: MockConfigEntry,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
    is_charging: bool,
    expected_state: str,
) -> None:
    """Test that the charging binary sensor reflects is_charging state changes."""
    with patch(
        "homeassistant.components.casper_glow.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await fire_callbacks(GlowState(is_charging=is_charging))
    state = hass.states.get(CHARGING_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_charging_ignores_none_state(
    hass: HomeAssistant,
    mock_casper_glow: MagicMock,
    mock_config_entry: MockConfigEntry,
    fire_callbacks: Callable[[GlowState], Awaitable[None]],
) -> None:
    """Test that a callback with is_charging=None does not overwrite the state."""
    with patch(
        "homeassistant.components.casper_glow.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    # Set a known value first
    await fire_callbacks(GlowState(is_charging=True))
    state = hass.states.get(CHARGING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # Callback with no is_charging data — state should remain unchanged
    await fire_callbacks(GlowState(is_on=True))
    state = hass.states.get(CHARGING_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
