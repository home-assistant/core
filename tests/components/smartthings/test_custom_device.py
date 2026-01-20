"""Test for the SmartThings custom device (Hot Water Mat)."""
from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smartthings.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_smartthings_entities

from tests.common import MockConfigEntry


@pytest.mark.parametrize("device_fixture", ["hot_water_mat"])
async def test_hot_water_mat_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities for the Hot Water Mat are created correctly."""
    await setup_integration(hass, mock_config_entry)

    # Check entities are created
    # Main Switch
    state = hass.states.get("switch.hot_water_mat_switch")
    assert state is not None
    assert state.state == "off"

    # Left Side
    state = hass.states.get("switch.hot_water_mat_left_side_switch")
    assert state is not None
    assert state.state == "off"
    
    state = hass.states.get("number.hot_water_mat_left_side_target_temperature")
    assert state is not None
    assert state.state == "28"
    assert state.attributes.get("min") == 28
    assert state.attributes.get("max") == 45
    
    state = hass.states.get("sensor.hot_water_mat_left_side_temperature")
    assert state is not None
    assert state.state == "28"

    # Right Side
    state = hass.states.get("switch.hot_water_mat_right_side_switch")
    assert state is not None
    assert state.state == "on"
    
    state = hass.states.get("number.hot_water_mat_right_side_target_temperature")
    assert state is not None
    assert state.state == "28.5"

    state = hass.states.get("sensor.hot_water_mat_right_side_temperature")
    assert state is not None
    assert state.state == "28.5"
