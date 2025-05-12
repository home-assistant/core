"""Test the Whirlpool Binary Sensor domain."""

import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration, snapshot_whirlpool_entities, trigger_attr_callback


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await init_integration(hass)
    snapshot_whirlpool_entities(hass, entity_registry, snapshot, Platform.BINARY_SENSOR)


@pytest.mark.parametrize(
    ("entity_id", "mock_fixture", "mock_method"),
    [
        ("binary_sensor.washer_door", "mock_washer_api", "get_door_open"),
        ("binary_sensor.dryer_door", "mock_dryer_api", "get_door_open"),
    ],
)
async def test_simple_binary_sensors(
    hass: HomeAssistant,
    entity_id: str,
    mock_fixture: str,
    mock_method: str,
    request: pytest.FixtureRequest,
) -> None:
    """Test simple binary sensors states."""
    mock_instance = request.getfixturevalue(mock_fixture)
    mock_method = getattr(mock_instance, mock_method)
    await init_integration(hass)

    mock_method.return_value = False
    await trigger_attr_callback(hass, mock_instance)
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    mock_method.return_value = True
    await trigger_attr_callback(hass, mock_instance)
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    mock_method.return_value = None
    await trigger_attr_callback(hass, mock_instance)
    state = hass.states.get(entity_id)
    assert state.state is STATE_UNKNOWN
