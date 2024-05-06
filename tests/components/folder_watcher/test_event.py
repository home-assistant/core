"""The event entity tests for Folder Watcher."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import create_file

from tests.common import MockConfigEntry, snapshot_platform


async def test_event_entity(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the event entity."""
    entry = load_int
    create_file("some text")
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
