"""Tests for the sensor platform of the A. O. Smith integration."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the setup of the sensor entity."""
    entry = entity_registry.async_get("sensor.my_water_heater_hot_water_availability")
    assert entry
    assert entry.unique_id == "hot_water_availability_junctionId"


async def test_state(
    hass: HomeAssistant, init_integration: MockConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test the state of the sensor entity."""
    state = hass.states.get("sensor.my_water_heater_hot_water_availability")
    assert state == snapshot
