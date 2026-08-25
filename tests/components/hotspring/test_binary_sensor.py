"""Tests for the Hot Spring binary sensor platform."""

from unittest.mock import MagicMock

from hotspring import Spa, SpaFailureState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the binary sensor platform state."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.BINARY_SENSOR]
    )
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("failure_state", "expected_state"),
    [
        (SpaFailureState.OK, STATE_OFF),
        (SpaFailureState.UNKNOWN, STATE_UNKNOWN),
    ],
)
async def test_problem_binary_sensor_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
    failure_state: SpaFailureState,
    expected_state: str,
) -> None:
    """Test problem binary sensor state mapping."""
    device_fixture.diagnostics.spa_failure_state = failure_state
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.BINARY_SENSOR]
    )
    state = hass.states.get("binary_sensor.connectedspa_ddeeff_problem")
    assert state is not None
    assert state.state == expected_state
