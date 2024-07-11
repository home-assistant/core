"""Tests for myuplink sensor module."""

from unittest.mock import MagicMock

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


# Test one entity from each of binary_sensor classes.
@pytest.mark.parametrize(
    ("entity_id", "friendly_name", "test_attributes", "expected_state"),
    [
        (
            "binary_sensor.gotham_city_pump_heating_medium_gp1",
            "Gotham City Pump: Heating medium (GP1)",
            True,
            STATE_ON,
        ),
        (
            "binary_sensor.gotham_city_connectivity",
            "Gotham City Connectivity",
            False,
            STATE_ON,
        ),
        (
            "binary_sensor.gotham_city_alarm",
            "Gotham City Pump: Alarm",
            False,
            STATE_OFF,
        ),
    ],
)
async def test_sensor_states(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    friendly_name: str,
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
            "friendly_name": friendly_name,
        }
