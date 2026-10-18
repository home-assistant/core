"""The event entity tests for Folder Watcher."""

import asyncio
from pathlib import Path

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_event_entity(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    tmp_path: Path,
) -> None:
    """Test the event entity."""
    entry = load_int
    await hass.async_block_till_done()

    # Watchdog delivers events from its own threads, so wait for the final one.
    moved = asyncio.Event()

    @callback
    def _async_state_changed(event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state and new_state.attributes.get("event_type") == "moved":
            moved.set()

    hass.bus.async_listen(EVENT_STATE_CHANGED, _async_state_changed)

    file = tmp_path.joinpath("hello.txt")
    file.write_text("Hello, world!")
    new_file = tmp_path.joinpath("hello2.txt")
    file.rename(new_file)

    async with asyncio.timeout(10):
        await moved.wait()

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert entity_entries

    def limit_attrs(prop, path):
        exclude_attrs = {
            "entity_id",
            "friendly_name",
            "folder",
            "path",
            "dest_folder",
            "dest_path",
            # The state is a strictly-increasing event timestamp; its exact
            # value depends on how many filesystem notifications the real
            # watchdog backend emits (varies by platform), so it is asserted
            # dynamically below instead of being pinned in the snapshot.
            "state",
        }
        return prop in exclude_attrs

    for entity_entry in entity_entries:
        assert entity_entry == snapshot(
            name=f"{entity_entry.unique_id}-entry", exclude=limit_attrs
        )
        assert (state := hass.states.get(entity_entry.entity_id))
        assert dt_util.parse_datetime(state.state) is not None
        assert state == snapshot(
            name=f"{entity_entry.unique_id}-state", exclude=limit_attrs
        )
