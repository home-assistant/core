"""Tests for the sensor platform of the A. O. Smith integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entity_id", "unique_id"),
    [
        (
            "sensor.my_water_heater_hot_water_availability",
            "hot_water_availability_junctionId",
        ),
        ("sensor.my_water_heater_energy_usage", "energy_usage_junctionId"),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    entity_id: str,
    unique_id: str,
) -> None:
    """Test the setup of the sensor entities."""
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == unique_id


@pytest.mark.parametrize(
    ("entity_id"),
    [
        "sensor.my_water_heater_hot_water_availability",
        "sensor.my_water_heater_energy_usage",
    ],
)
async def test_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the state of the sensor entities."""
    state = hass.states.get(entity_id)
    assert state == snapshot
