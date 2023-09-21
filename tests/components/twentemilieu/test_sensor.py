"""Tests for the Twente Milieu sensors."""
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.twente_milieu_christmas_tree_pickup",
        "sensor.twente_milieu_non_recyclable_waste_pickup",
        "sensor.twente_milieu_organic_waste_pickup",
        "sensor.twente_milieu_packages_waste_pickup",
        "sensor.twente_milieu_paper_waste_pickup",
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the Twente Milieu waste pickup sensors."""
    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot
