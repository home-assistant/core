"""Tests for the KEBA charging station in each captured station state."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.keba.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize("corpus", ["p30_plugged.json", "p30_charging.json"])
async def test_states_per_station_state(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the entity states for a car plugged in, and for a car charging."""
    entity_ids = sorted(
        entry.entity_id
        for entry in entity_registry.entities.values()
        if entry.platform == DOMAIN
    )
    assert len(entity_ids) == 10
    for entity_id in entity_ids:
        assert hass.states.get(entity_id) == snapshot(name=entity_id)
