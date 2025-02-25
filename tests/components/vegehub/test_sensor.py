"""Unit tests for the VegeHub integration's sensor.py."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    vegehub_config_entry,  # Use the fixture
) -> None:
    """Test all entities."""
    await snapshot_platform(
        hass, entity_registry, snapshot, vegehub_config_entry.entry_id
    )
