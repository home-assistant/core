"""Community-Edition migration: adopt entities from the legacy ``truenas`` domain.

After the integration domain is renamed from ``truenas`` to ``truenas_ce``
(breaking 2.0.0) a fresh config entry would create brand-new entities with new
entity_ids, orphaning the recorder history of the old ones. This module makes
the rename transparent: on first setup of the renamed integration it adopts the
old entities' entity_ids (so states + long-term statistics reconnect), persists
a reverse map + a snapshot of the old configuration, and disables — but never
deletes — the legacy config entry so the whole step can be rolled back.

While ``DOMAIN == LEGACY_DOMAIN`` (i.e. before the rename actually lands) every
public entry point here is a no-op, so the module is safe to ship ahead of the
rename. Forward adoption runs in two phases around the platform setup:

1. :func:`async_adopt_legacy_entities` (before platforms load) frees the old
   entity_ids and remembers them.
2. :func:`finalize_legacy_adoption` (after platforms load) re-attaches each
   freed entity_id to the matching freshly-created entity.

:func:`async_rollback_to_legacy` reverses the whole operation.
"""

from logging import getLogger
import os
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry, ConfigEntryDisabler
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    LEGACY_DOMAIN,
    MIGRATION_BACKUP_KEY,
    MIGRATION_DONE,
    MIGRATION_LEGACY_CONFIG,
    MIGRATION_LEGACY_ENTRY_ID,
    MIGRATION_RECORDS,
    MIGRATION_RESOLVED_UNIQUE_IDS,
)

_LOGGER = getLogger(__name__)

# Public migration guide, linked from the post-migration success notification.
_GUIDE_URL = (
    "https://github.com/kayl-codes/homeassistant-truenas/blob/master/docs/migration.md"
)
# Stable per-entry notification id so the success message is shown once, not stacked.
_NOTIFY_PREFIX = "truenas_ce_migration"
# object_id prefix for the temporary ids used while un-permuting adopted entity_ids.
_TEMP_OBJECT_PREFIX = "truenas_ce_mig_"

# Record keys (kept short; persisted verbatim on the config entry's data).
_R_UNIQUE_ID = "unique_id"
_R_ENTITY_DOMAIN = "entity_domain"
_R_ENTITY_ID = "entity_id"
_R_NAME = "name"
_R_ICON = "icon"
_R_AREA = "area_id"
_R_DISABLED = "disabled_user"

# Belt-and-suspenders safety snapshot written to ``.storage`` before the registry
# is mutated. Unlike the reverse map on the config entry, this standalone file
# survives even if the (new) config entry is later deleted, so the adoption can be
# reconstructed by hand in the worst case.
_BACKUP_KEY_PREFIX = "truenas_ce_migration_backup"
_BACKUP_VERSION = 1


# ---------------------------
#   Forward adoption
# ---------------------------
async def async_adopt_legacy_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> list[dict[str, Any]]:
    """Release the legacy entities' entity_ids for adoption by this entry.

    Returns the list of freed records for :func:`finalize_legacy_adoption` to
    re-attach once the new platforms have created their entities. Idempotent:
    after the first successful run (``MIGRATION_DONE``) it returns an empty list.
    Inert while ``DOMAIN == LEGACY_DOMAIN``.
    """
    if DOMAIN == LEGACY_DOMAIN or config_entry.data.get(MIGRATION_DONE):
        return []

    legacy_entry = _find_legacy_entry(hass, config_entry)
    records: list[dict[str, Any]] = []
    backup_key: str | None = None

    if legacy_entry is not None:
        # Disable the legacy entry first so its coordinator stops and cannot
        # re-discover (re-add) the entities we are about to release.
        if legacy_entry.disabled_by is None:
            await hass.config_entries.async_set_disabled_by(
                legacy_entry.entry_id, ConfigEntryDisabler.USER
            )
        ent_reg = er.async_get(hass)
        # Capture the records read-only, write the safety snapshot, and only then
        # mutate the registry — so a failed backup never leaves a half-freed state.
        records = _collect_legacy_records(ent_reg, legacy_entry)
        backup_key = await _write_migration_backup(
            hass, config_entry, legacy_entry, records
        )
        _remove_legacy_entities(ent_reg, records)
        _LOGGER.info(
            "Adopted %d entities from legacy '%s' entry %s",
            len(records),
            LEGACY_DOMAIN,
            legacy_entry.entry_id,
        )

    _persist_migration_state(hass, config_entry, legacy_entry, records, backup_key)
    return records


def pending_legacy_records(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> list[dict[str, Any]]:
    """Return the reverse-map records not yet resolved.

    Used to retry :func:`finalize_legacy_adoption` on every setup for a record
    left pending by an earlier run -- its entity was disabled or its monitored
    group off, so it did not exist yet. ``MIGRATION_RECORDS`` itself is the
    complete, never-pruned history (needed intact for a full rollback); a
    record is excluded here once its unique_id is recorded in
    ``MIGRATION_RESOLVED_UNIQUE_IDS`` by :func:`_mark_resolved_records`, so an
    already-resolved (or since manually renamed) record is never retried.
    """
    if DOMAIN == LEGACY_DOMAIN:
        return []

    resolved = set(config_entry.data.get(MIGRATION_RESOLVED_UNIQUE_IDS, []))
    return [
        record
        for record in config_entry.data.get(MIGRATION_RECORDS, [])
        if record[_R_UNIQUE_ID] not in resolved
    ]


def finalize_legacy_adoption(
    hass: HomeAssistant, config_entry: ConfigEntry, records: list[dict[str, Any]]
) -> None:
    """Re-attach the freed legacy entity_ids to the new entities.

    Called after the platforms have been set up so the new (``truenas_ce``)
    entities already exist in the registry. The caller must only pass records
    that are actually safe to (re)attach -- freshly adopted ones from
    :func:`async_adopt_legacy_entities`, or still-pending ones from
    :func:`pending_legacy_records`. A record whose entity reclaims its target
    id this pass is recorded as resolved (see :func:`_mark_resolved_records`),
    so a later manual rename is never fought by a subsequent retry.
    """
    if DOMAIN == LEGACY_DOMAIN or not records:
        return

    ent_reg = er.async_get(hass)
    pairs = [
        (new_id, record[_R_ENTITY_ID], record)
        for record in records
        if (
            new_id := ent_reg.async_get_entity_id(
                record[_R_ENTITY_DOMAIN], DOMAIN, record[_R_UNIQUE_ID]
            )
        )
        is not None
    ]
    _remap_and_restore(ent_reg, pairs)
    _mark_resolved_records(hass, config_entry, records)


def _mark_resolved_records(
    hass: HomeAssistant, config_entry: ConfigEntry, attempted: list[dict[str, Any]]
) -> None:
    """Record which of ``attempted`` reclaimed their target id, for pending_legacy_records.

    A record must never be retried once resolved -- a later retry could
    otherwise force back a user's manual rename. ``MIGRATION_RECORDS`` itself
    is left untouched (rollback needs the complete original history); records
    still unresolved (entity absent, or a real collision under a different
    id) are simply not added here, so a future retry can pick them up again.
    """
    ent_reg = er.async_get(hass)
    newly_resolved = {
        record[_R_UNIQUE_ID]
        for record in attempted
        if ent_reg.async_get_entity_id(
            record[_R_ENTITY_DOMAIN], DOMAIN, record[_R_UNIQUE_ID]
        )
        == record[_R_ENTITY_ID]
    }
    if not newly_resolved:
        return

    already_resolved = set(config_entry.data.get(MIGRATION_RESOLVED_UNIQUE_IDS, []))
    if not newly_resolved <= already_resolved:
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                MIGRATION_RESOLVED_UNIQUE_IDS: sorted(
                    already_resolved | newly_resolved
                ),
            },
        )


def _find_legacy_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> ConfigEntry | None:
    """Find the old ``truenas`` config entry matching this one (by host).

    Only an exact host match is adopted. A single-legacy-entry fallback used
    to adopt regardless of host, but that also fired for "migrate manually"
    and for a plain new entry added while an unrelated legacy entry for a
    *different* box happened to exist -- disabling and stripping that
    unrelated entry's entities. ``async_step_migrate_import`` copies the
    legacy entry's host verbatim into the new entry, so the normal takeover
    path still matches exactly here as long as the user keeps the pre-filled
    host.
    """
    host = config_entry.data.get(CONF_HOST)
    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(LEGACY_DOMAIN)
            if entry.data.get(CONF_HOST) == host
        ),
        None,
    )


def _collect_legacy_records(
    ent_reg: er.EntityRegistry, legacy_entry: ConfigEntry
) -> list[dict[str, Any]]:
    """Snapshot every registry entry of the legacy config entry (read-only)."""
    return [
        {
            _R_UNIQUE_ID: entry.unique_id,
            _R_ENTITY_DOMAIN: entry.domain,
            _R_ENTITY_ID: entry.entity_id,
            _R_NAME: entry.name,
            _R_ICON: entry.icon,
            _R_AREA: entry.area_id,
            _R_DISABLED: entry.disabled_by == er.RegistryEntryDisabler.USER,
        }
        for entry in er.async_entries_for_config_entry(ent_reg, legacy_entry.entry_id)
    ]


def _remove_legacy_entities(
    ent_reg: er.EntityRegistry, records: list[dict[str, Any]]
) -> None:
    """Free the recorded entity_ids for adoption.

    Removing the registry entry frees its entity_id and any user overrides but
    leaves the long-term statistics in the recorder DB untouched, so reusing
    the same entity_id later reconnects state + history.
    """
    for record in records:
        ent_reg.async_remove(record[_R_ENTITY_ID])


async def _write_migration_backup(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    legacy_entry: ConfigEntry,
    records: list[dict[str, Any]],
) -> str | None:
    """Write a human-readable safety snapshot before the registry is mutated.

    Best effort: a failed write only drops the extra safety net (the reverse map
    on the config entry remains the primary undo), so it must not abort the
    migration. Returns the ``.storage`` key on success, else ``None``.
    """
    timestamp = dt_util.utcnow().strftime("%Y%m%d_%H%M%S")
    store: Store[dict[str, Any]] = Store(
        hass, _BACKUP_VERSION, f"{_BACKUP_KEY_PREFIX}_{timestamp}"
    )
    payload = {
        "created": dt_util.utcnow().isoformat(),
        "ce_entry_id": config_entry.entry_id,
        "legacy_entry_id": legacy_entry.entry_id,
        "legacy_config": {
            "data": dict(legacy_entry.data),
            "options": dict(legacy_entry.options),
        },
        "records": records,
    }
    try:
        await store.async_save(payload)
    except (OSError, ValueError, TypeError) as err:
        _LOGGER.warning("Could not write CE migration backup snapshot: %s", err)
        return None
    _LOGGER.info("Wrote CE migration backup snapshot '%s'", store.key)
    await _remove_backups(hass, store.key)
    return store.key


async def _remove_backups(hass: HomeAssistant, keep_key: str | None) -> None:
    """Remove migration backup snapshots from ``.storage``.

    Scans the ``.storage`` directory for ``truenas_ce_migration_backup_*`` stores
    and removes every one except ``keep_key`` — pass ``None`` to remove all. Used
    to keep only the latest snapshot after a write, and to drop all of them on
    rollback. Listing the directory (rather than trusting a stored key) makes the
    rollback cleanup robust even if the key was never persisted. Best effort —
    failures are logged, never raised.
    """
    storage_dir = hass.config.path(".storage")

    def _targets() -> list[str]:
        try:
            return [
                name
                for name in os.listdir(storage_dir)
                if name.startswith(_BACKUP_KEY_PREFIX) and name != keep_key
            ]
        except OSError:
            return []

    for key in await hass.async_add_executor_job(_targets):
        try:
            await Store(hass, _BACKUP_VERSION, key).async_remove()
            _LOGGER.debug("Removed CE migration backup snapshot '%s'", key)
        except OSError as err:
            _LOGGER.warning("Could not remove CE migration backup '%s': %s", key, err)


def _persist_migration_state(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    legacy_entry: ConfigEntry | None,
    records: list[dict[str, Any]],
    backup_key: str | None,
) -> None:
    """Store the idempotency flag, reverse map and legacy snapshot on the entry."""
    new_data = {
        **config_entry.data,
        MIGRATION_DONE: True,
        MIGRATION_RECORDS: records,
    }
    if legacy_entry is not None:
        new_data[MIGRATION_LEGACY_ENTRY_ID] = legacy_entry.entry_id
        new_data[MIGRATION_LEGACY_CONFIG] = {
            "data": dict(legacy_entry.data),
            "options": dict(legacy_entry.options),
        }
    if backup_key:
        new_data[MIGRATION_BACKUP_KEY] = backup_key
    hass.config_entries.async_update_entry(config_entry, data=new_data)


def _remap_and_restore(
    ent_reg: er.EntityRegistry, pairs: list[tuple[str, str, dict[str, Any]]]
) -> None:
    """Move each entity from its current id onto its target id, then restore overrides.

    ``pairs`` is ``(current_entity_id, target_entity_id, record)``. A naive
    one-by-one rename fails when the ids form a *permutation* (e.g. unstable
    Linux disk ``sd*`` letters that re-ordered since the legacy entities were
    created: ``sda``→``sdb`` while ``sdb``→``sda``), because each target is still
    held by another member of the cycle. So this runs two passes: first park
    every entity that isn't already on its target on a free temporary id —
    vacating all target ids — then move each onto its target. History reconnects
    by the entity's final id matching the recorder statistics, so only the end
    state matters.
    """
    parked: list[tuple[str, str, dict[str, Any]]] = []
    counter = 0
    for current_id, target_id, record in pairs:
        if current_id == target_id:
            parked.append((current_id, target_id, record))
            continue
        temp_id, counter = _temp_entity_id(ent_reg, current_id, counter)
        ent_reg.async_update_entity(current_id, new_entity_id=temp_id)
        parked.append((temp_id, target_id, record))

    for current_id, target_id, record in parked:
        final_id = current_id
        if current_id != target_id and ent_reg.async_get(target_id) is None:
            ent_reg.async_update_entity(current_id, new_entity_id=target_id)
            final_id = target_id
        elif current_id != target_id:
            _LOGGER.warning(
                "CE migration: could not restore id %s (still occupied); left as %s",
                target_id,
                current_id,
            )
        _restore_overrides(ent_reg, final_id, record)


def _temp_entity_id(
    ent_reg: er.EntityRegistry, like_entity_id: str, start: int
) -> tuple[str, int]:
    """Return an unused temporary entity_id in the same domain, and the next counter."""
    domain = like_entity_id.split(".", 1)[0]
    counter = start
    while True:
        candidate = f"{domain}.{_TEMP_OBJECT_PREFIX}{counter}"
        counter += 1
        if ent_reg.async_get(candidate) is None:
            return candidate, counter


def _restore_overrides(
    ent_reg: er.EntityRegistry, entity_id: str, record: dict[str, Any]
) -> None:
    """Re-apply the user's name/icon/area/disabled overrides to an adopted entity."""
    updates: dict[str, Any] = {}
    if record.get(_R_NAME):
        updates["name"] = record[_R_NAME]
    if record.get(_R_ICON):
        updates["icon"] = record[_R_ICON]
    if record.get(_R_AREA):
        updates["area_id"] = record[_R_AREA]
    if record.get(_R_DISABLED):
        updates["disabled_by"] = er.RegistryEntryDisabler.USER
    if updates:
        ent_reg.async_update_entity(entity_id, **updates)


# ---------------------------
#   Post-migration notification
# ---------------------------
def async_notify_migration_result(
    hass: HomeAssistant, config_entry: ConfigEntry, records: list[dict[str, Any]]
) -> None:
    """Surface a one-time success notification after a legacy adoption.

    Validates the adoption with a few cheap registry/state checks and reports
    them, links the migration guide and points at the rollback fallback. Only
    fires on the run that actually adopted entities (``records`` non-empty),
    which is the first successful migration. Inert before the rename.
    """
    if DOMAIN == LEGACY_DOMAIN or not records:
        return

    ent_reg = er.async_get(hass)
    total = len(records)
    reconnected, pending, mismatched = _classify_reconnection(ent_reg, records)
    _log_reconnection(pending, mismatched)

    history_label = f"History reconnected: {reconnected}/{total}"
    if pending:
        history_label += f" ({len(pending)} inactive/disabled — history kept)"

    legacy_id = config_entry.data.get(MIGRATION_LEGACY_ENTRY_ID)
    legacy_entry = hass.config_entries.async_get_entry(legacy_id) if legacy_id else None
    checks = {
        "entities": (total > 0, f"Entities adopted: {total}"),
        # A still-pending entity is fine (its history is preserved); only a real
        # id collision (mismatched) is a problem.
        "history": (not mismatched, history_label),
        "disabled": (
            legacy_entry is not None and legacy_entry.disabled_by is not None,
            "Previous TrueNAS integration disabled (not deleted)",
        ),
        "backup": (
            bool(config_entry.data.get(MIGRATION_BACKUP_KEY)),
            "Safety backup written",
        ),
        "rollback": (
            bool(legacy_id and config_entry.data.get(MIGRATION_RECORDS)),
            "Rollback available",
        ),
    }
    persistent_notification.async_create(
        hass,
        _build_migration_message(total, checks),
        title="TrueNAS CE — migration complete",
        notification_id=f"{_NOTIFY_PREFIX}_{config_entry.entry_id}",
    )


def _classify_reconnection(
    ent_reg: er.EntityRegistry, records: list[dict[str, Any]]
) -> tuple[int, list[str], list[str]]:
    """Split adopted records into reconnected / pending / mismatched buckets.

    - **reconnected**: a new entity exists and reclaimed the original entity_id.
    - **pending**: no new entity yet (a disabled entity, a disabled monitored
      group, or an object not currently present) — the recorder history stays and
      re-attaches when the entity reappears.
    - **mismatched**: a new entity exists but under a *different* id (a real id
      collision that left the history detached).
    """
    reconnected = 0
    pending: list[str] = []
    mismatched: list[str] = []
    for record in records:
        target_id = record[_R_ENTITY_ID]
        new_id = ent_reg.async_get_entity_id(
            record[_R_ENTITY_DOMAIN], DOMAIN, record[_R_UNIQUE_ID]
        )
        if new_id == target_id:
            reconnected += 1
        elif new_id is None:
            pending.append(target_id)
        else:
            mismatched.append(f"{target_id} -> {new_id}")
    return reconnected, pending, mismatched


def _log_reconnection(pending: list[str], mismatched: list[str]) -> None:
    """Log which adopted entities did not (yet) reclaim their original id."""
    if pending:
        _LOGGER.info(
            "CE migration: %d adopted entities not yet recreated (history kept, "
            "re-attaches when they reappear): %s",
            len(pending),
            ", ".join(sorted(pending)),
        )
    if mismatched:
        _LOGGER.warning(
            "CE migration: %d adopted entities could not reclaim their id: %s",
            len(mismatched),
            ", ".join(sorted(mismatched)),
        )


def _build_migration_message(total: int, checks: dict[str, tuple[bool, str]]) -> str:
    """Render the markdown body of the post-migration success notification."""
    lines = "\n".join(
        f"- {'✅' if ok else '⚠️'} {label}" for ok, label in checks.values()
    )
    noun = "entity" if total == 1 else "entities"
    return (
        "**TrueNAS Community Edition migration complete.**\n\n"
        f"{total} {noun} adopted with full history; the previous TrueNAS "
        "integration was disabled (not deleted).\n\n"
        f"**Validation**\n{lines}\n\n"
        "To undo this, press the **Roll back migration** button on the TrueNAS "
        "device — it opens a confirmation. This works only while you keep the old "
        "TrueNAS integration; once you delete it, the migration is permanent.\n\n"
        f"[Open the migration guide]({_GUIDE_URL})"
    )


# ---------------------------
#   Rollback
# ---------------------------
async def async_rollback_to_legacy(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Reverse the adoption: hand the entity_ids back to the legacy entry.

    Removes this (``truenas_ce``) config entry first to free the adopted
    entity_ids, then re-enables the disabled legacy ``truenas`` entry so it
    reclaims them, and finally restores the user overrides. Returns ``False`` if
    there is nothing to roll back (no legacy bridge left). Inert before rename.
    """
    if DOMAIN == LEGACY_DOMAIN:
        return False

    legacy_entry_id = config_entry.data.get(MIGRATION_LEGACY_ENTRY_ID)
    if not legacy_entry_id:
        return False
    if hass.config_entries.async_get_entry(legacy_entry_id) is None:
        return False

    records = config_entry.data.get(MIGRATION_RECORDS, [])

    _LOGGER.info(
        "Rolling back '%s' adoption: returning %d entities to legacy entry %s",
        DOMAIN,
        len(records),
        legacy_entry_id,
    )

    # 1. Remove this entry first so the adopted entity_ids are freed and the
    #    integration is unloaded.
    await hass.config_entries.async_remove(config_entry.entry_id)
    # 2. Re-enable the legacy entry; it re-creates its entities at their current
    #    names, freeing the original ids for the remap below.
    await hass.config_entries.async_set_disabled_by(legacy_entry_id, None)
    # 3. Restore the original legacy entity_ids (permutation-safe, e.g. disk sd*
    #    re-lettering) and the user overrides, mirroring the forward adoption.
    ent_reg = er.async_get(hass)
    pairs = [
        (legacy_id, record[_R_ENTITY_ID], record)
        for record in records
        if (
            legacy_id := ent_reg.async_get_entity_id(
                record[_R_ENTITY_DOMAIN], LEGACY_DOMAIN, record[_R_UNIQUE_ID]
            )
        )
        is not None
    ]
    _remap_and_restore(ent_reg, pairs)

    # The migration is fully undone — drop all safety snapshots.
    await _remove_backups(hass, keep_key=None)

    return True
