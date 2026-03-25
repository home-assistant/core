"""Test the Casper Glow binary sensor platform."""

from unittest.mock import MagicMock, patch

from pycasperglow import GlowState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "binary_sensor.jar_dimming_paused"


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
async def test_binary_sensor_state_update(
    hass: HomeAssistant,
    mock_casper_glow: MagicMock,
    mock_config_entry: MockConfigEntry,
    is_paused: bool,
    expected_state: str,
) -> None:
    """Test that the binary sensor reflects is_paused state changes."""
    with patch(
        "homeassistant.components.casper_glow.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    cb = mock_casper_glow.register_callback.call_args[0][0]

    cb(GlowState(is_paused=is_paused))
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_binary_sensor_ignores_none_paused_state(
    hass: HomeAssistant,
    mock_casper_glow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a callback with is_paused=None does not overwrite the state."""
    with patch(
        "homeassistant.components.casper_glow.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    cb = mock_casper_glow.register_callback.call_args[0][0]

    # Set a known value first
    cb(GlowState(is_paused=True))
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # Callback with no is_paused data — state should remain unchanged
    cb(GlowState(is_on=True))
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
