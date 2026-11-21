"""Ordered config-entry writeback using Core's public mutation APIs."""

import asyncio
from collections.abc import Callable
import logging
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
    ConfigSubentry,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.discovery_flow import DiscoveryKey
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.storage import Store
from homeassistant.util import ulid as ulid_util

from ._proto import sandbox_pb2 as pb
from .channel import Channel
from .messages import MSG_ENTRY_UPDATE, decode_json_dict, encode_json

_LOGGER = logging.getLogger(__name__)
_FIELDS = (
    "data",
    "options",
    "title",
    "unique_id",
    "version",
    "minor_version",
    "pref_disable_new_entities",
    "pref_disable_polling",
    "discovery_keys",
)


def entry_snapshot(entry: ConfigEntry) -> dict[str, Any]:
    """Capture detached, wire-safe mutable configuration, including subentry IDs."""
    stored = entry.as_dict()
    return decode_json_dict(
        encode_json(
            {
                **{key: stored[key] for key in _FIELDS},
                "subentries": {
                    item.subentry_id: item.as_dict()
                    for item in entry.subentries.values()
                },
            }
        )
    )


def _map_subentry_ids(snapshot: dict[str, Any], ids: dict[str, str]) -> dict[str, Any]:
    subentries = {}
    for key, value in snapshot["subentries"].items():
        if value["subentry_id"] != key:
            raise HomeAssistantError("Invalid subentry ID")
        mapped_id = ids.get(key, key)
        if mapped_id in subentries:
            raise HomeAssistantError("Conflicting subentry IDs")
        subentries[mapped_id] = value | {"subentry_id": mapped_id}
    return snapshot | {"subentries": subentries}


def apply_entry_update(
    hass: HomeAssistant,
    entry: ConfigEntry,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    """Check every changed field before committing through the public APIs."""
    current = entry_snapshot(entry)
    if before.keys() != current.keys() or after.keys() != current.keys():
        raise HomeAssistantError("Invalid entry update fields")
    changes = {key: after[key] for key in _FIELDS if before[key] != after[key]}
    for key, value in changes.items():
        if current[key] != before[key] and current[key] != value:
            raise HomeAssistantError(
                f"Conflicting entry update: {key}; reload required"
            )
    old_subs, new_subs = before["subentries"], after["subentries"]
    if not isinstance(old_subs, dict) or not isinstance(new_subs, dict):
        raise HomeAssistantError("Invalid subentries")
    changed_ids = {
        key
        for key in old_subs.keys() | new_subs.keys()
        if old_subs.get(key) != new_subs.get(key)
    }
    merged = dict(current["subentries"])
    for key in changed_ids:
        if merged.get(key) != old_subs.get(key) and merged.get(key) != new_subs.get(
            key
        ):
            raise HomeAssistantError("Conflicting subentry update; reload required")
        if key in new_subs:
            merged[key] = new_subs[key]
        else:
            merged.pop(key, None)
    prepared = {}
    unique_ids: set[str] = set()
    for key, value in merged.items():
        if (
            value.keys()
            != {"subentry_id", "data", "title", "unique_id", "subentry_type"}
            or value["subentry_id"] != key
        ):
            raise HomeAssistantError("Invalid subentry fields")
        sub = ConfigSubentry(**(value | {"data": MappingProxyType(value["data"])}))
        if sub.unique_id is not None:
            if sub.unique_id in unique_ids:
                raise HomeAssistantError("Duplicate subentry unique ID")
            unique_ids.add(sub.unique_id)
        if (
            key in entry.subentries
            and entry.subentries[key].subentry_type != sub.subentry_type
        ):
            raise HomeAssistantError("Cannot change subentry type")
        prepared[key] = sub
    if "discovery_keys" in changes:
        changes["discovery_keys"] = MappingProxyType(
            {
                key: tuple(DiscoveryKey.from_json_dict(item) for item in items)
                for key, items in changes["discovery_keys"].items()
            }
        )
    entries = hass.config_entries
    # Remove first so an update can reuse a deleted subentry's unique ID.
    for key in entry.subentries.keys() - prepared.keys():
        entries.async_remove_subentry(entry, key)
    for key in changed_ids & prepared.keys():
        sub = prepared[key]
        if key in entry.subentries:
            entries.async_update_subentry(
                entry,
                entry.subentries[key],
                data=sub.data,
                title=sub.title,
                unique_id=sub.unique_id,
            )
        else:
            entries.async_add_subentry(entry, sub)
    entries.async_update_entry(entry, **changes)


class EntrySync:
    """Observe owned entries and send ordered, acknowledged changes to the peer."""

    def __init__(
        self,
        hass: HomeAssistant,
        channel: Channel,
        owns: Callable[[ConfigEntry], bool],
        *,
        assign_subentry_ids: bool = False,
    ) -> None:
        """Bind the observer and RPC handler to one live channel."""
        self.hass = hass
        self.channel = channel
        self._owns = owns
        self._assign_subentry_ids = assign_subentry_ids
        self._subentry_ids: dict[str, dict[str, str]] = {}
        self._subentry_lock = asyncio.Lock()
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._pending: dict[str, asyncio.Task[None]] = {}
        self._errors: dict[str, Exception] = {}
        self._applying = False
        self._unsub = async_dispatcher_connect(
            hass, SIGNAL_CONFIG_ENTRY_CHANGED, self._changed
        )
        channel.register(MSG_ENTRY_UPDATE, self._handle_update)

    def _subentry_store(self, entry_id: str) -> Store[dict[str, str]]:
        return Store(
            self.hass, 1, f"sandbox.subentry_ids.{entry_id}", atomic_writes=True
        )

    async def _async_load_subentry_ids(self, entry_id: str) -> dict[str, str]:
        if entry_id not in self._subentry_ids:
            self._subentry_ids[entry_id] = (
                await self._subentry_store(entry_id).async_load() or {}
            )
        return self._subentry_ids[entry_id]

    def local_subentry_id(self, entry_id: str, remote_id: str) -> str:
        """Resolve worker aliases for host registry ownership."""
        return self._subentry_ids.get(entry_id, {}).get(remote_id, remote_id)

    def remote_subentry_id(self, entry_id: str, local_id: str) -> str:
        """Keep flow context in the worker's ID namespace."""
        reverse = {
            local: remote
            for remote, local in self._subentry_ids.get(entry_id, {}).items()
        }
        return reverse.get(local_id, local_id)

    def _remote_snapshot(
        self, entry_id: str, snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        return _map_subentry_ids(
            snapshot,
            {
                local: remote
                for remote, local in self._subentry_ids.get(entry_id, {}).items()
            },
        )

    async def async_prepare_setup(self, entry: ConfigEntry, msg: pb.EntrySetup) -> None:
        """Restore worker-local IDs, including references saved by the integration."""
        async with self._subentry_lock:
            await self._async_load_subentry_ids(entry.entry_id)
            snapshot = self._remote_snapshot(entry.entry_id, entry_snapshot(entry))
            msg.subentries = encode_json(list(snapshot["subentries"].values()))
            self.track(entry)

    async def _async_remove_subentry_ids(self, entry_id: str) -> None:
        async with self._subentry_lock:
            self._subentry_ids.pop(entry_id, None)
            await self._subentry_store(entry_id).async_remove()

    @callback
    def track(self, entry: ConfigEntry) -> None:
        """Establish the baseline sent in entry_setup or flow_init."""
        self._snapshots[entry.entry_id] = entry_snapshot(entry)
        self._errors.pop(entry.entry_id, None)

    @callback
    def forget(self, entry_id: str) -> None:
        """Stop mirroring an unloaded entry."""
        self._snapshots.pop(entry_id, None)
        self._errors.pop(entry_id, None)

    @callback
    def _changed(self, change: ConfigEntryChange, entry: ConfigEntry) -> None:
        if (
            change is ConfigEntryChange.REMOVED
            and self._assign_subentry_ids
            and self._owns(entry)
        ):
            self.forget(entry.entry_id)
            self.hass.async_create_task(self._async_remove_subentry_ids(entry.entry_id))
            return
        if (
            self._applying
            or change is not ConfigEntryChange.UPDATED
            or not self._owns(entry)
        ):
            return
        entry_id = entry.entry_id
        if (
            before := self._snapshots.get(entry_id)
        ) is None or entry_id in self._errors:
            return
        after = entry_snapshot(entry)
        if before == after:
            return
        self._snapshots[entry_id] = after
        previous = self._pending.get(entry_id)
        message = pb.EntryUpdate(
            entry_id=entry_id,
            before=encode_json(self._remote_snapshot(entry_id, before)),
            after=encode_json(self._remote_snapshot(entry_id, after)),
        )
        self._pending[entry_id] = self.hass.async_create_task(
            self._send(message, previous), f"sandbox config update {entry_id}"
        )

    async def _send(
        self, message: pb.EntryUpdate, previous: asyncio.Task[None] | None
    ) -> None:
        if previous is not None:
            await previous
        if message.entry_id in self._errors:
            return
        try:
            await self.channel.call(MSG_ENTRY_UPDATE, message, timeout=30)
        except Exception as err:  # noqa: BLE001
            self._errors[message.entry_id] = err
            _LOGGER.error(
                "Sandbox config update failed for %s; reload required", message.entry_id
            )

    async def flush(self, entry_id: str | None = None) -> None:
        """Wait for updates queued before this call and surface failed writeback."""
        keys = (
            [entry_id]
            if entry_id is not None
            else list(self._pending.keys() | self._errors.keys())
        )
        for key in keys:
            while (task := self._pending.get(key)) is not None:
                await task
                if self._pending.get(key) is task:
                    self._pending.pop(key, None)
            if key in self._errors:
                raise HomeAssistantError(
                    "Sandbox config update failed; reload required"
                ) from self._errors[key]

    async def _handle_update(self, msg: pb.EntryUpdate) -> pb.EntryUpdateResult:
        entry = self.hass.config_entries.async_get_entry(msg.entry_id)
        if (
            entry is None
            or not self._owns(entry)
            or msg.entry_id not in self._snapshots
        ):
            raise HomeAssistantError("Entry update does not belong to this sandbox")
        before, after = decode_json_dict(msg.before), decode_json_dict(msg.after)
        async with self._subentry_lock:
            if self._assign_subentry_ids:
                ids = await self._async_load_subentry_ids(entry.entry_id)
                updated_ids = dict(ids)
                for remote_id in (
                    after["subentries"].keys() - before["subentries"].keys()
                ):
                    if remote_id not in updated_ids:
                        if remote_id in entry.subentries:
                            raise HomeAssistantError("Subentry ID already in use")
                        updated_ids[remote_id] = ulid_util.ulid_now()
                before = _map_subentry_ids(before, updated_ids)
                after = _map_subentry_ids(after, updated_ids)
                if updated_ids != ids:
                    # Persist aliases before canonical entries can reference them.
                    await self._subentry_store(entry.entry_id).async_save(updated_ids)
                    # Store logs write failures without raising them.
                    if (
                        await self._subentry_store(entry.entry_id).async_load()
                        != updated_ids
                    ):
                        raise HomeAssistantError("Could not save subentry IDs")
                    self._subentry_ids[entry.entry_id] = updated_ids
            if (
                self.hass.config_entries.async_get_entry(msg.entry_id) is not entry
                or not self._owns(entry)
                or msg.entry_id not in self._snapshots
            ):
                raise HomeAssistantError("Entry update does not belong to this sandbox")
            self._applying = True
            try:
                apply_entry_update(self.hass, entry, before, after)
                self._snapshots[entry.entry_id] = entry_snapshot(entry)
            finally:
                self._applying = False
        return pb.EntryUpdateResult()

    async def async_stop(self) -> None:
        """Detach observers and finish queued configuration writes."""
        self._unsub()
        try:
            await self.flush()
        except HomeAssistantError:
            _LOGGER.error("Stopping sandbox with unacknowledged config changes")
