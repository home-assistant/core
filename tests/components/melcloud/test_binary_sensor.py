"""Test the MELCloud binary sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_get_devices")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all binary sensor entities with snapshot."""
    await setup_platform(hass, mock_config_entry, [Platform.BINARY_SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_get_devices")
@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        ("binary_sensor.ecodan_boiler", STATE_ON),
        ("binary_sensor.ecodan_booster_heater_1", STATE_OFF),
        ("binary_sensor.ecodan_immersion_heater", STATE_OFF),
        ("binary_sensor.ecodan_water_pump_1", STATE_ON),
        ("binary_sensor.ecodan_water_pump_2", STATE_OFF),
        ("binary_sensor.ecodan_3_way_valve", STATE_ON),
    ],
)
async def test_atw_binary_sensor_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test ATW binary sensor entity states."""
    await setup_platform(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found"
    assert state.state == expected_state
