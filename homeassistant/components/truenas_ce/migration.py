"""Community-Edition migration: adopt entities from the legacy ``truenas`` domain."""

from logging import getLogger
import os
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.components.diagnostics import async_redact_data
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
    MIGRATION_LEFT_BEHIND_DOMAINS,
    MIGRATION_LEGACY_CONFIG,
    MIGRATION_LEGACY_ENTRY_ID,
    MIGRATION_RECORDS,
    MIGRATION_RESOLVED_UNIQUE_IDS,
    PLATFORMS,
    TO_REDACT,
)
from .helper import sanitize_host

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

# Standalone `.storage` snapshot; unlike the on-entry reverse map, it survives
# even if the (new) config entry is later deleted.
_BACKUP_KEY_PREFIX = "truenas_ce_migration_backup"
_BACKUP_VERSION = 1


# ---------------------------
#   Forward adoption
# ---------------------------
async def async_adopt_legacy_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> list[dict[str, Any]]:
    """Release the legacy entities' entity_ids for adoption by this entry.

    Returns the freed records for :func:`finalize_legacy_adoption` to re-attach.
    Idempotent (no-op once ``MIGRATION_DONE``); inert before the rename.
    """
    if DOMAIN == LEGACY_DOMAIN or config_entry.data.get(MIGRATION_DONE):
        return []

    legacy_entry = _find_legacy_entry(hass, config_entry)
    records: list[dict[str, Any]] = []
    backup_key: str | None = None
    left_behind: list[str] = []

    if legacy_entry is not None:
        # Disable first so its coordinator can't re-add entities as we release
        # them; abort without persisting MIGRATION_DONE if that fails.
        disabled = legacy_entry.disabled_by is not None or (
            await hass.config_entries.async_set_disabled_by(
                legacy_entry.entry_id, ConfigEntryDisabler.USER
            )
        )
        if not disabled:
            _LOGGER.error(
                "Adoption aborted: legacy '%s' entry %s could not be disabled;"
                " entities were left in place and will be retried on next setup",
                LEGACY_DOMAIN,
                legacy_entry.entry_id,
            )
            return []
        ent_reg = er.async_get(hass)
        # Write the backup before mutating the registry, so a failed backup
        # never leaves a half-freed state.
        records = _collect_legacy_records(ent_reg, legacy_entry)
        left_behind = _collect_left_behind_domains(ent_reg, legacy_entry)
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
        if left_behind:
            # These stay registered on the now-disabled legacy entry (see
            # _collect_legacy_records) and go inactive along with it -- surfaced
            # to the user via the post-migration notification, see
            # async_notify_migration_result.
            _LOGGER.warning(
                "CE migration: legacy '%s' entry %s also has %s entities this "
                "build does not adopt yet; they remain registered but inactive "
                "until a later release adds that platform",
                LEGACY_DOMAIN,
                legacy_entry.entry_id,
                ", ".join(left_behind),
            )

    _persist_migration_state(
        hass, config_entry, legacy_entry, records, backup_key, left_behind
    )
    return records


def pending_legacy_records(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> list[dict[str, Any]]:
    """Return the reverse-map records not yet resolved.

    Retried by :func:`finalize_legacy_adoption` on every setup. Records marked
    resolved in ``MIGRATION_RESOLVED_UNIQUE_IDS`` are excluded so a manual
    rename is never retried; ``MIGRATION_RECORDS`` itself stays untouched since
    a full rollback needs the complete history.
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

    Called after platform setup, once the new (``truenas_ce``) entities exist.
    Callers must only pass records safe to (re)attach — from
    :func:`async_adopt_legacy_entities` or :func:`pending_legacy_records`.
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
    """Record which of ``attempted`` reclaimed their target id.

    Once resolved a record must never be retried, or a later retry could force
    back a user's manual rename. ``MIGRATION_RECORDS`` itself stays untouched
    since rollback needs the complete original history.
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

    Only an exact (sanitized, case-insensitive) host match is adopted — a
    single-legacy-entry fallback used to match regardless of host, but that
    could disable and strip entities of an unrelated legacy entry for a
    different box.
    """
    host = sanitize_host(config_entry.data.get(CONF_HOST, ""))
    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(LEGACY_DOMAIN)
            if sanitize_host(entry.data.get(CONF_HOST, "")) == host
        ),
        None,
    )


def _collect_legacy_records(
    ent_reg: er.EntityRegistry, legacy_entry: ConfigEntry
) -> list[dict[str, Any]]:
    """Snapshot the legacy config entry's registry entries this build can adopt.

    Only entities in a currently loaded platform (``PLATFORMS``) are included —
    a platform this build doesn't set up has no replacement entity to reclaim
    a freed id, so those entries are left on the still-disabled legacy entry
    for a later release to pick up.
    """
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
        if entry.domain in PLATFORMS
    ]


def _collect_left_behind_domains(
    ent_reg: er.EntityRegistry, legacy_entry: ConfigEntry
) -> list[str]:
    """Return the legacy entry's entity domains this build cannot adopt yet.

    The complement of :func:`_collect_legacy_records`'s ``PLATFORMS`` filter --
    these entries stay registered on the still-disabled legacy entry rather
    than being freed, since there is no replacement entity to reclaim their
    id. Reported to the user via :func:`async_notify_migration_result` so the
    gap is disclosed instead of silent.
    """
    return sorted(
        {
            entry.domain
            for entry in er.async_entries_for_config_entry(
                ent_reg, legacy_entry.entry_id
            )
            if entry.domain not in PLATFORMS
        }
    )


def _remove_legacy_entities(
    ent_reg: er.EntityRegistry, records: list[dict[str, Any]]
) -> None:
    """Free the recorded entity_ids for adoption.

    Removing the registry entry leaves recorder long-term statistics
    untouched, so reusing the same entity_id later reconnects the history.
    """
    for record in records:
        ent_reg.async_remove(record[_R_ENTITY_ID])


def _redacted_legacy_snapshot(legacy_entry: ConfigEntry) -> dict[str, Any]:
    """Return the legacy entry's data/options with sensitive fields redacted.

    Neither snapshot is ever read back by :func:`async_rollback_to_legacy`
    (it re-enables the still-existing legacy entry instead), so there's no
    reason for either copy to carry a live API key.
    """
    return {
        "data": async_redact_data(dict(legacy_entry.data), TO_REDACT),
        "options": dict(legacy_entry.options),
    }


def _entry_backup_prefix(entry_id: str) -> str:
    """Return the per-entry ``.storage`` key prefix for migration backups.

    Namespaced by entry id so concurrent migrations never collide, and
    cleanup of one entry's snapshots can never prune another's.
    """
    return f"{_BACKUP_KEY_PREFIX}_{entry_id}"


async def _write_migration_backup(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    legacy_entry: ConfigEntry,
    records: list[dict[str, Any]],
) -> str | None:
    """Write a human-readable safety snapshot before the registry is mutated.

    Best effort: a failed write only drops the extra safety net (the on-entry
    reverse map remains the primary undo), so it must not abort the migration.
    """
    now = dt_util.utcnow()
    prefix = _entry_backup_prefix(config_entry.entry_id)
    store: Store[dict[str, Any]] = Store(
        hass, _BACKUP_VERSION, f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}"
    )
    payload = {
        "created": now.isoformat(),
        "ce_entry_id": config_entry.entry_id,
        "legacy_entry_id": legacy_entry.entry_id,
        "legacy_config": _redacted_legacy_snapshot(legacy_entry),
        "records": records,
    }
    try:
        await store.async_save(payload)
    except (OSError, ValueError, TypeError) as err:
        _LOGGER.warning("Could not write CE migration backup snapshot: %s", err)
        return None
    _LOGGER.info("Wrote CE migration backup snapshot '%s'", store.key)
    await _remove_backups(hass, prefix, store.key)
    return store.key


async def _remove_backups(
    hass: HomeAssistant, prefix: str, keep_key: str | None
) -> None:
    """Remove this entry's migration backup snapshots from ``.storage``.

    Removes every stored file matching ``prefix`` except ``keep_key`` (``None``
    removes all). Scans the directory rather than trusting a stored key, so
    cleanup on rollback works even if the key was never persisted. Best
    effort — failures are logged, never raised.
    """
    storage_dir = hass.config.path(".storage")

    def _targets() -> list[str]:
        try:
            return [
                name
                for name in os.listdir(storage_dir)
                if name.startswith(prefix) and name != keep_key
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
    left_behind: list[str] | None = None,
) -> None:
    """Store the idempotency flag, reverse map and legacy snapshot on the entry."""
    new_data = {
        **config_entry.data,
        MIGRATION_DONE: True,
        MIGRATION_RECORDS: records,
    }
    if legacy_entry is not None:
        new_data[MIGRATION_LEGACY_ENTRY_ID] = legacy_entry.entry_id
        new_data[MIGRATION_LEGACY_CONFIG] = _redacted_legacy_snapshot(legacy_entry)
    if backup_key:
        new_data[MIGRATION_BACKUP_KEY] = backup_key
    if left_behind:
        new_data[MIGRATION_LEFT_BEHIND_DOMAINS] = left_behind
    hass.config_entries.async_update_entry(config_entry, data=new_data)


def _remap_and_restore(
    ent_reg: er.EntityRegistry, pairs: list[tuple[str, str, dict[str, Any]]]
) -> None:
    """Move each entity from its current id onto its target id, then restore overrides.

    ``pairs`` is ``(current_entity_id, target_entity_id, record)``. Two passes:
    park every entity on a free temp id first, then move onto the target. A
    single pass would fail when ids form a permutation (e.g. re-ordered disk
    ``sd*`` letters: ``sda``→``sdb`` while ``sdb``→``sda``), since each target
    is still held by another member of the cycle.
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
    if record.get(_R_NAME) is not None:
        updates["name"] = record[_R_NAME]
    if record.get(_R_ICON) is not None:
        updates["icon"] = record[_R_ICON]
    if record.get(_R_AREA) is not None:
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

    Only fires on the run that actually adopted entities (first successful
    migration); inert before the rename. Also calls out any entity domains
    outside ``PLATFORMS`` found on the legacy entry (see
    :func:`_collect_left_behind_domains`) -- they stay registered but inactive
    on the now-disabled legacy entry, so the user is told why rather than
    finding those entities silently gone.
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
    if left_behind := config_entry.data.get(MIGRATION_LEFT_BEHIND_DOMAINS, []):
        checks["left_behind"] = (
            False,
            f"Not yet migrated: {', '.join(left_behind)} entities remain on the "
            "disabled previous integration until a future update adds that "
            "platform",
        )
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

    ``pending`` means no new entity yet (disabled, or its group off); history
    stays and re-attaches once it reappears. ``mismatched`` means a real id
    collision left the history detached.
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
        "To undo this, go to **Settings → Repairs**, open the "
        "**TrueNAS CE migration — rollback available** repair, and choose "
        "**Roll back to the previous integration**. This works only while you "
        "keep the old TrueNAS integration; once you delete it, the migration "
        "is permanent.\n\n"
        f"[Open the migration guide]({_GUIDE_URL})"
    )


# ---------------------------
#   Rollback
# ---------------------------
async def async_rollback_to_legacy(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Reverse the adoption: hand the entity_ids back to the legacy entry.

    Re-enables the legacy entry first, while this entry still exists as a
    fallback, and only tears this one down once the legacy setup is confirmed
    working. Returns ``False`` if there's nothing to roll back or the legacy
    entry failed to set up (nothing is torn down in that case).
    """
    if DOMAIN == LEGACY_DOMAIN:
        return False

    legacy_entry_id = config_entry.data.get(MIGRATION_LEGACY_ENTRY_ID)
    if not legacy_entry_id:
        return False
    if hass.config_entries.async_get_entry(legacy_entry_id) is None:
        return False

    records = config_entry.data.get(MIGRATION_RECORDS, [])
    prefix = _entry_backup_prefix(config_entry.entry_id)

    _LOGGER.info(
        "Rolling back '%s' adoption: returning %d entities to legacy entry %s",
        DOMAIN,
        len(records),
        legacy_entry_id,
    )

    # 1. Re-enable the legacy entry first (it settles for temp ids until step 3
    #    frees the originals). Checking the result before tearing anything down
    #    lets a failed setup (e.g. device unreachable) abort with both entries
    #    intact, instead of leaving the user with neither.
    if not await hass.config_entries.async_set_disabled_by(legacy_entry_id, None):
        _LOGGER.error(
            "Rollback aborted: legacy '%s' entry %s failed to set up; "
            "the '%s' entry was left in place",
            LEGACY_DOMAIN,
            legacy_entry_id,
            DOMAIN,
        )
        return False

    # 2. Remove this entry, freeing the adopted entity_ids.
    await hass.config_entries.async_remove(config_entry.entry_id)
    # 3. Restore the original legacy entity_ids and user overrides.
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

    # The migration is fully undone — drop this entry's safety snapshots.
    await _remove_backups(hass, prefix, keep_key=None)

    return True
