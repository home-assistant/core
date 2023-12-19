"""Tests for binary sensor entities provided by the Tailwind integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_number_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor entities provided by the Tailwind integration."""
    for entity_id in (
        "binary_sensor.door_1_operational_status",
        "binary_sensor.door_2_operational_status",
    ):
        assert (state := hass.states.get(entity_id))
        assert snapshot == state

        assert (entity_entry := entity_registry.async_get(state.entity_id))
        assert snapshot == entity_entry

        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert snapshot == device_entry
