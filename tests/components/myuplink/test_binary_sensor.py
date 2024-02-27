"""Tests for myuplink sensor module."""

from unittest.mock import MagicMock  # noqa: I001

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

import pytest


# Test one entity from each of binary_sensor classes.
@pytest.mark.parametrize(
    ("entity_id", "test_attributes", "expected_state"),
    [
        ("binary_sensor.f730_cu_3x400v_pump_heating_medium_gp1", True, STATE_ON),
        ("binary_sensor.f730_cu_3x400v_connectivity", False, STATE_ON),
        ("binary_sensor.f730_cu_3x400v_alarm", False, STATE_OFF),
    ],
)
async def test_sensor_states(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    test_attributes: bool,
    expected_state: str,
) -> None:
    """Test sensor state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    if test_attributes:
        assert state.attributes == {
            "friendly_name": "F730 CU 3x400V Pump: Heating medium (GP1)",
        }
