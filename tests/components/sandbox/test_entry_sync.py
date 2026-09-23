"""Configuration writeback, conflict detection, and subentry identity."""

from collections.abc import AsyncIterator
from pathlib import Path
from types import MappingProxyType

from hass_client.channel import ChannelRemoteError
from hass_client.entry_runner import _entry_from_proto
from hass_client.entry_sync import EntrySync as ClientEntrySync
from hass_client.flow_runner import FlowRunner
from hass_client.testing._inproc import make_inproc_channel_pair
import pytest

from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.entry_sync import EntrySync, entry_snapshot
from homeassistant.components.sandbox.messages import encode_json, entry_to_setup_proto
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.discovery_flow import DiscoveryKey

from tests.common import MockConfigEntry


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Canonical entry with an existing subentry and discovery identity."""
    entry = MockConfigEntry(
        domain="test",
        sandbox="built-in",
        data={"token": "original"},
        pref_disable_new_entities=True,
        pref_disable_polling=True,
        discovery_keys={
            "zeroconf": (
                DiscoveryKey(domain="zeroconf", key=("one", "two"), version=1),
            )
        },
        subentries_data=[
            {
                "subentry_id": "original",
                "subentry_type": "device",
                "data": {"host": "old"},
                "title": "Original",
                "unique_id": "one",
            }
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def peers(
    hass: HomeAssistant, tmp_path: Path, entry: MockConfigEntry
) -> AsyncIterator[tuple[EntrySync, ClientEntrySync, ConfigEntry]]:
    """Join distinct HA instances through the production protobuf codec."""
    runner = await FlowRunner.create(config_dir=str(tmp_path))
    main_channel, worker_channel = make_inproc_channel_pair(group="built-in")
    main = EntrySync(hass, main_channel, lambda item: item.sandbox == "built-in")
    worker = ClientEntrySync(runner.hass, worker_channel, lambda item: True)
    child_entry = _entry_from_proto(entry_to_setup_proto(entry))
    runner.hass.config_entries._entries[child_entry.entry_id] = child_entry
    main.track(entry)
    worker.track(child_entry)
    main_channel.start()
    worker_channel.start()
    try:
        yield main, worker, child_entry
    finally:
        await main.async_stop()
        await worker.async_stop()
        await main_channel.close()
        await worker_channel.close()
        await runner.async_stop()


async def test_roundtrip_and_ordered_writeback(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    peers: tuple[EntrySync, ClientEntrySync, ConfigEntry],
) -> None:
    """Token refresh and schema migration reach the canonical entry in order."""
    main, worker, child = peers
    assert child.subentries["original"].data == {"host": "old"}
    assert child.pref_disable_new_entities is True
    assert child.pref_disable_polling is True
    assert child.discovery_keys == entry.discovery_keys
    worker.hass.config_entries.async_update_entry(child, data={"token": "first"})
    worker.hass.config_entries.async_update_entry(
        child,
        data={"token": "second"},
        version=2,
        minor_version=3,
        unique_id="migrated",
        title="New title",
    )
    await worker.flush()
    assert entry.data == {"token": "second"}
    assert (entry.version, entry.minor_version, entry.unique_id, entry.title) == (
        2,
        3,
        "migrated",
        "New title",
    )
    hass.config_entries.async_update_entry(entry, options={"poll": 60})
    await main.flush()
    assert child.options == {"poll": 60}
    assert _entry_from_proto(entry_to_setup_proto(entry)).data == {"token": "second"}


async def test_subentry_add_update_remove(
    entry: MockConfigEntry, peers: tuple[EntrySync, ClientEntrySync, ConfigEntry]
) -> None:
    """Stable subentry IDs and subsequent edits survive both directions."""
    main, worker, child = peers
    subentry = ConfigSubentry(
        data=MappingProxyType({"host": "new"}),
        subentry_type="device",
        title="Second",
        unique_id="two",
    )
    worker.hass.config_entries.async_add_subentry(child, subentry)
    await worker.flush()
    assert entry.subentries[subentry.subentry_id].as_dict() == subentry.as_dict()
    main.hass.config_entries.async_update_subentry(
        entry,
        entry.subentries[subentry.subentry_id],
        title="Renamed",
        data={"host": "updated"},
    )
    await main.flush()
    assert child.subentries[subentry.subentry_id].title == "Renamed"
    assert child.subentries[subentry.subentry_id].data == {"host": "updated"}
    worker.hass.config_entries.async_remove_subentry(child, "original")
    await worker.flush()
    assert set(entry.subentries) == {subentry.subentry_id}


async def test_concurrent_unrelated_edits(
    entry: MockConfigEntry, peers: tuple[EntrySync, ClientEntrySync, ConfigEntry]
) -> None:
    """Concurrent edits of different fields merge without an echo loop."""
    main, worker, child = peers
    main.hass.config_entries.async_update_entry(entry, title="Main title")
    worker.hass.config_entries.async_update_entry(child, data={"token": "refreshed"})
    await worker.flush()
    await main.flush()
    assert entry_snapshot(entry) == entry_snapshot(child)
    assert entry.title == "Main title"
    assert entry.data == {"token": "refreshed"}


async def test_conflicting_edits_fail_without_overwrite(
    entry: MockConfigEntry, peers: tuple[EntrySync, ClientEntrySync, ConfigEntry]
) -> None:
    """Neither endpoint silently overwrites a conflicting acknowledged value."""
    main, worker, child = peers
    main.hass.config_entries.async_update_entry(entry, data={"token": "main"})
    worker.hass.config_entries.async_update_entry(child, data={"token": "worker"})
    with pytest.raises(HomeAssistantError, match="reload required"):
        await worker.flush()
    with pytest.raises(HomeAssistantError, match="reload required"):
        await main.flush()
    assert entry.data == {"token": "main"}
    assert child.data == {"token": "worker"}


async def test_foreign_entry_rejected(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    peers: tuple[EntrySync, ClientEntrySync, ConfigEntry],
) -> None:
    """A worker cannot update a local entry through the configuration API."""
    _main, worker, _child = peers
    foreign = MockConfigEntry(domain="test", data={"private": True})
    foreign.add_to_hass(hass)
    before = entry_snapshot(foreign)
    after = before | {"title": "Changed"}
    with pytest.raises(ChannelRemoteError, match="does not belong"):
        await worker.channel.call(
            "sandbox/entry_update",
            pb.EntryUpdate(
                entry_id=foreign.entry_id,
                before=encode_json(before),
                after=encode_json(after),
            ),
        )
    assert entry_snapshot(foreign) == before
