"""Tests for the Rainforest RAVEn sensors."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_entry")
async def test_sensors(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors."""
    assert len(hass.states.async_all()) == 5

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)
