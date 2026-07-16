"""Staged, rollback-aware migration from legacy NuHeat entries."""

from collections.abc import Mapping
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
import logging
from types import MappingProxyType
from typing import Any

from chemelex_nuheat import Thermostat

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .account_identity import (
    InvalidAccountSubjectError,
    account_subject_from_entry_data,
)
from .const import CONF_SERIAL_NUMBER, DOMAIN
from .registry_migration import (
    DeviceAssociationSnapshot,
    EntityAssociationSnapshot,
    build_registry_snapshots,
    restore_registry_snapshots,
    transfer_registry_ownership,
    validate_registry_snapshots,
    verify_registry_ownership,
)

LEGACY_CONFIG_ENTRY_VERSION = 1
OAUTH_CONFIG_ENTRY_VERSION = 3

CONF_MIGRATION_STATE = "migration_state"
CONF_MIGRATION_ANCHOR_ENTRY_ID = "migration_anchor_entry_id"
CONF_MIGRATION_SERIAL_NUMBER = "migration_serial_number"
CONF_MIGRATION_VALIDATED_SERIALS = "migration_validated_serials"
MIGRATION_STATE_IN_PROGRESS = "in_progress"
MIGRATION_STATE_PENDING_CLEANUP = "pending_cleanup"

ISSUE_CLEANUP_INCOMPLETE = "migration_cleanup_incomplete"
ISSUE_ROLLBACK_FAILED = "migration_rollback_failed"

_LOGGER = logging.getLogger(__name__)
_MIGRATION_RELOAD_ACTIVE: ContextVar[bool] = ContextVar(
    "nuheat_migration_reload_active", default=False
)


class MigrationPreflightError(RuntimeError):
    """Local migration state failed validation before mutation."""


class MigrationAccountMismatchError(MigrationPreflightError):
    """The authenticated account does not contain the initiating thermostat."""


class MigrationExecutionError(RuntimeError):
    """Migration failed and any possible rollback has been attempted."""


@dataclass(frozen=True, slots=True)
class ConfigEntrySnapshot:
    """Original mutable fields of one config entry."""

    entry_id: str
    data: Mapping[str, Any]
    title: str
    unique_id: str | None
    version: int


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    """Immutable output of remote validation and local preflight."""

    initiating_entry_id: str
    anchor_entry_id: str
    matching_legacy_entry_ids: tuple[str, ...]
    redundant_entry_ids: tuple[str, ...]
    validated_serials: frozenset[str]
    migrated_serials: frozenset[str]
    serial_entry_ids: tuple[tuple[str, str | None], ...]
    account_unique_id: str
    account_title: str
    original_anchor_data: Mapping[str, Any]
    original_anchor_title: str
    original_anchor_unique_id: str | None
    original_anchor_version: int
    redundant_entry_snapshots: tuple[ConfigEntrySnapshot, ...]
    entity_snapshots: tuple[EntityAssociationSnapshot, ...]
    device_snapshots: tuple[DeviceAssociationSnapshot, ...]


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """Describe the committed or rollback-safe migration outcome."""

    anchor_entry: ConfigEntry[Any]
    removed_entry_ids: tuple[str, ...]
    pending_cleanup_entry_ids: tuple[str, ...]
    migrated_serials: frozenset[str]
    cleanup_complete: bool


@dataclass(frozen=True, slots=True)
class _CleanupFailure:
    """Internal cleanup result when a removal call failed."""

    removed_entry_ids: tuple[str, ...]
    pending_entry_ids: tuple[str, ...]


def _immutable_data(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return a detached read-only config data snapshot."""
    return MappingProxyType(deepcopy(dict(data)))


def _entry_snapshot(entry: ConfigEntry[Any]) -> ConfigEntrySnapshot:
    return ConfigEntrySnapshot(
        entry_id=entry.entry_id,
        data=_immutable_data(entry.data),
        title=entry.title,
        unique_id=entry.unique_id,
        version=entry.version,
    )


def is_legacy_entry_data(data: Mapping[str, Any]) -> bool:
    """Return whether data has the obsolete per-thermostat credential schema."""
    return CONF_TOKEN not in data and all(
        key in data for key in (CONF_USERNAME, CONF_PASSWORD, CONF_SERIAL_NUMBER)
    )


def is_legacy_entry(entry: ConfigEntry[Any]) -> bool:
    """Return whether a config entry requires interactive OAuth migration."""
    return is_legacy_entry_data(entry.data)


def is_pending_cleanup_entry(entry: ConfigEntry[Any]) -> bool:
    """Return whether an entry is a non-secret deferred cleanup marker."""
    return entry.data.get(CONF_MIGRATION_STATE) == MIGRATION_STATE_PENDING_CLEANUP


def is_migration_anchor(entry: ConfigEntry[Any]) -> bool:
    """Return whether an OAuth anchor has incomplete migration cleanup."""
    return entry.data.get(CONF_MIGRATION_STATE) == MIGRATION_STATE_IN_PROGRESS


def migration_reload_active() -> bool:
    """Return whether setup is part of controlled migration verification."""
    return _MIGRATION_RELOAD_ACTIVE.get()


def _legacy_serial(entry: ConfigEntry[Any]) -> str | None:
    value = entry.data.get(CONF_SERIAL_NUMBER)
    return value if isinstance(value, str) and value else None


def _pending_serial(entry: ConfigEntry[Any]) -> str | None:
    value = entry.data.get(CONF_MIGRATION_SERIAL_NUMBER)
    return value if isinstance(value, str) and value else None


def _oauth_entry_subject(entry: ConfigEntry[Any]) -> str | None:
    """Return a stored OAuth subject without exposing token contents."""
    try:
        return account_subject_from_entry_data(entry.data)
    except InvalidAccountSubjectError:
        return None


def _issue_id(issue_type: str, anchor_entry_id: str) -> str:
    return f"{issue_type}_{anchor_entry_id}"


def _create_repair_issue(
    hass: HomeAssistant, anchor_entry_id: str, issue_type: str
) -> None:
    ir.async_create_issue(
        hass,
        DOMAIN,
        _issue_id(issue_type, anchor_entry_id),
        is_fixable=False,
        is_persistent=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.ERROR,
        translation_key=issue_type,
    )


def _delete_repair_issue(
    hass: HomeAssistant, anchor_entry_id: str, issue_type: str
) -> None:
    ir.async_delete_issue(hass, DOMAIN, _issue_id(issue_type, anchor_entry_id))


def build_migration_plan(
    hass: HomeAssistant,
    initiating_entry: ConfigEntry[Any],
    *,
    account_unique_id: str,
    account_title: str,
    thermostats: list[Thermostat],
) -> MigrationPlan:
    """Build and preflight an immutable plan without local mutations."""
    domain_entries = hass.config_entries.async_entries(DOMAIN)
    if initiating_entry not in domain_entries or not is_legacy_entry(initiating_entry):
        raise MigrationPreflightError("Initiating legacy entry is no longer present")

    initiating_serial = _legacy_serial(initiating_entry)
    validated_serials = frozenset(
        thermostat.serial_number for thermostat in thermostats
    )
    if initiating_serial is None or initiating_serial not in validated_serials:
        raise MigrationAccountMismatchError

    account_entries = [
        entry
        for entry in domain_entries
        if entry.entry_id != initiating_entry.entry_id
        and CONF_TOKEN in entry.data
        and not is_pending_cleanup_entry(entry)
        and (
            entry.unique_id == account_unique_id
            or _oauth_entry_subject(entry) == account_unique_id
        )
    ]
    if len(account_entries) > 1:
        raise MigrationPreflightError("Duplicate NuHeat account entry appeared")
    anchor_entry = account_entries[0] if account_entries else initiating_entry

    legacy_by_serial: dict[str, ConfigEntry[Any]] = {}
    for entry in domain_entries:
        if not is_legacy_entry(entry):
            continue
        serial = _legacy_serial(entry)
        if serial is None:
            raise MigrationPreflightError("Legacy NuHeat entry has no valid serial")
        if serial in validated_serials:
            if serial in legacy_by_serial:
                raise MigrationPreflightError("Duplicate legacy thermostat entry")
            legacy_by_serial[serial] = entry

    matching_entries = tuple(legacy_by_serial.values())
    if initiating_entry not in matching_entries:
        raise MigrationAccountMismatchError
    redundant_entries = tuple(
        entry for entry in matching_entries if entry.entry_id != anchor_entry.entry_id
    )

    serial_entry_ids = tuple(
        (
            serial,
            (
                legacy_entry.entry_id
                if (legacy_entry := legacy_by_serial.get(serial)) is not None
                and legacy_entry.entry_id != anchor_entry.entry_id
                else None
            ),
        )
        for serial in sorted(validated_serials)
    )
    entity_snapshots, device_snapshots = build_registry_snapshots(
        hass,
        serial_entry_ids=serial_entry_ids,
        anchor_entry_id=anchor_entry.entry_id,
    )

    return MigrationPlan(
        initiating_entry_id=initiating_entry.entry_id,
        anchor_entry_id=anchor_entry.entry_id,
        matching_legacy_entry_ids=tuple(entry.entry_id for entry in matching_entries),
        redundant_entry_ids=tuple(entry.entry_id for entry in redundant_entries),
        validated_serials=validated_serials,
        migrated_serials=frozenset(legacy_by_serial),
        serial_entry_ids=serial_entry_ids,
        account_unique_id=account_unique_id,
        account_title=account_title,
        original_anchor_data=_immutable_data(anchor_entry.data),
        original_anchor_title=anchor_entry.title,
        original_anchor_unique_id=anchor_entry.unique_id,
        original_anchor_version=anchor_entry.version,
        redundant_entry_snapshots=tuple(
            _entry_snapshot(entry) for entry in redundant_entries
        ),
        entity_snapshots=entity_snapshots,
        device_snapshots=device_snapshots,
    )


def validate_migration_plan(hass: HomeAssistant, plan: MigrationPlan) -> None:
    """Recheck every preflight assumption immediately before mutation."""
    anchor = hass.config_entries.async_get_entry(plan.anchor_entry_id)
    if anchor is None:
        raise MigrationPreflightError("NuHeat anchor disappeared after preflight")
    if (
        dict(anchor.data) != dict(plan.original_anchor_data)
        or anchor.title != plan.original_anchor_title
        or anchor.unique_id != plan.original_anchor_unique_id
        or anchor.version != plan.original_anchor_version
    ):
        raise MigrationPreflightError("NuHeat anchor changed after preflight")

    for snapshot in plan.redundant_entry_snapshots:
        entry = hass.config_entries.async_get_entry(snapshot.entry_id)
        if entry is None:
            raise MigrationPreflightError("Redundant NuHeat entry disappeared")
        if (
            dict(entry.data) != dict(snapshot.data)
            or entry.title != snapshot.title
            or entry.unique_id != snapshot.unique_id
            or entry.version != snapshot.version
        ):
            raise MigrationPreflightError("Redundant NuHeat entry changed")

    duplicates = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id != plan.anchor_entry_id
        and CONF_TOKEN in entry.data
        and not is_pending_cleanup_entry(entry)
        and (
            entry.unique_id == plan.account_unique_id
            or _oauth_entry_subject(entry) == plan.account_unique_id
        )
    ]
    if duplicates:
        raise MigrationPreflightError("Duplicate NuHeat account entry appeared")

    validate_registry_snapshots(hass, plan.entity_snapshots, plan.device_snapshots)


def _migration_marker_data(
    data: Mapping[str, Any], plan: MigrationPlan
) -> dict[str, Any]:
    marked = dict(data)
    marked[CONF_MIGRATION_STATE] = MIGRATION_STATE_IN_PROGRESS
    marked[CONF_MIGRATION_VALIDATED_SERIALS] = sorted(plan.validated_serials)
    return marked


def _pending_cleanup_data(anchor_entry_id: str, serial_number: str) -> dict[str, str]:
    return {
        CONF_MIGRATION_STATE: MIGRATION_STATE_PENDING_CLEANUP,
        CONF_MIGRATION_ANCHOR_ENTRY_ID: anchor_entry_id,
        CONF_MIGRATION_SERIAL_NUMBER: serial_number,
    }


async def _reload_anchor(hass: HomeAssistant, plan: MigrationPlan) -> None:
    """Reload the OAuth anchor while suppressing automatic cleanup."""
    token = _MIGRATION_RELOAD_ACTIVE.set(True)
    try:
        if not await hass.config_entries.async_reload(plan.anchor_entry_id):
            raise MigrationExecutionError("NuHeat anchor reload failed")
    finally:
        _MIGRATION_RELOAD_ACTIVE.reset(token)


def verify_migration_plan_result(hass: HomeAssistant, plan: MigrationPlan) -> None:
    """Verify the loaded anchor exposes every remotely validated thermostat."""
    anchor = hass.config_entries.async_get_entry(plan.anchor_entry_id)
    if anchor is None or anchor.state is not ConfigEntryState.LOADED:
        raise MigrationExecutionError("NuHeat anchor did not load")
    coordinator_data = anchor.runtime_data.coordinator.data or {}
    if not plan.validated_serials.issubset(coordinator_data):
        raise MigrationExecutionError("NuHeat anchor omitted expected thermostats")
    verify_registry_ownership(
        hass,
        anchor_entry_id=plan.anchor_entry_id,
        serial_numbers=plan.validated_serials,
    )


async def rollback_migration_plan(hass: HomeAssistant, plan: MigrationPlan) -> bool:
    """Restore all reversible local mutations without recreating old records."""
    rollback_failed = False
    anchor = hass.config_entries.async_get_entry(plan.anchor_entry_id)
    if anchor is not None and anchor.state is ConfigEntryState.LOADED:
        try:
            if not await hass.config_entries.async_unload(anchor.entry_id):
                rollback_failed = True
        except Exception:  # noqa: BLE001
            rollback_failed = True

    try:
        restore_registry_snapshots(hass, plan.entity_snapshots, plan.device_snapshots)
    except Exception:  # noqa: BLE001
        rollback_failed = True

    try:
        anchor = hass.config_entries.async_get_entry(plan.anchor_entry_id)
        if anchor is None:
            rollback_failed = True
        else:
            hass.config_entries.async_update_entry(
                anchor,
                data=dict(plan.original_anchor_data),
                title=plan.original_anchor_title,
                unique_id=plan.original_anchor_unique_id,
                version=plan.original_anchor_version,
            )
        for snapshot in plan.redundant_entry_snapshots:
            entry = hass.config_entries.async_get_entry(snapshot.entry_id)
            if entry is None:
                rollback_failed = True
                continue
            hass.config_entries.async_update_entry(
                entry,
                data=dict(snapshot.data),
                title=snapshot.title,
                unique_id=snapshot.unique_id,
                version=snapshot.version,
            )
    except Exception:  # noqa: BLE001
        rollback_failed = True

    if rollback_failed:
        _LOGGER.error(
            "NuHeat migration rollback was incomplete; restoration from backup "
            "may be required"
        )
        _create_repair_issue(hass, plan.anchor_entry_id, ISSUE_ROLLBACK_FAILED)
        return False

    _delete_repair_issue(hass, plan.anchor_entry_id, ISSUE_ROLLBACK_FAILED)
    return True


async def _cleanup_plan_entries(
    hass: HomeAssistant, plan: MigrationPlan
) -> _CleanupFailure | None:
    removed: list[str] = []
    for entry_id in plan.redundant_entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            removed.append(entry_id)
            continue
        try:
            await hass.config_entries.async_remove(entry_id)
        except Exception:  # noqa: BLE001
            pending = tuple(
                pending_id
                for pending_id in plan.redundant_entry_ids
                if hass.config_entries.async_get_entry(pending_id) is not None
            )
            return _CleanupFailure(tuple(removed), pending)
        removed.append(entry_id)
    return None


def _finish_anchor_data(
    hass: HomeAssistant,
    anchor: ConfigEntry[Any],
    oauth_data: Mapping[str, Any],
    plan: MigrationPlan,
) -> None:
    hass.config_entries.async_update_entry(
        anchor,
        data=_migration_marker_data(oauth_data, plan),
        title=plan.account_title,
        unique_id=plan.account_unique_id,
        version=OAUTH_CONFIG_ENTRY_VERSION,
    )


def _require_config_entry(hass: HomeAssistant, entry_id: str) -> ConfigEntry[Any]:
    """Return a config entry or fail the active migration."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise MigrationExecutionError(
            "Redundant NuHeat entry disappeared during execution"
        )
    return entry


def _verify_validated_serials(
    validated_serials: frozenset[str], coordinator_data: Mapping[str, Thermostat]
) -> None:
    """Verify that a refreshed account still contains all validated thermostats."""
    if not validated_serials.issubset(coordinator_data):
        raise MigrationExecutionError("NuHeat restart verification omitted devices")


async def execute_migration_plan(
    hass: HomeAssistant,
    plan: MigrationPlan,
    *,
    oauth_data: Mapping[str, Any],
) -> MigrationResult:
    """Execute a validated plan with rollback before the removal boundary."""
    validate_migration_plan(hass, plan)
    anchor = hass.config_entries.async_get_entry(plan.anchor_entry_id)
    assert anchor is not None

    try:
        transfer_registry_ownership(
            hass,
            anchor_entry_id=plan.anchor_entry_id,
            entity_snapshots=plan.entity_snapshots,
            device_snapshots=plan.device_snapshots,
        )

        hybrid_data = dict(plan.original_anchor_data)
        hybrid_data.update(oauth_data)
        hass.config_entries.async_update_entry(
            anchor,
            data=_migration_marker_data(hybrid_data, plan),
            title=plan.account_title,
            unique_id=plan.account_unique_id,
            version=OAUTH_CONFIG_ENTRY_VERSION,
        )

        serial_by_entry = {
            entry_id: serial
            for serial, entry_id in plan.serial_entry_ids
            if entry_id is not None
        }
        for snapshot in plan.redundant_entry_snapshots:
            redundant_entry = _require_config_entry(hass, snapshot.entry_id)
            hass.config_entries.async_update_entry(
                redundant_entry,
                data=_pending_cleanup_data(
                    plan.anchor_entry_id, serial_by_entry[snapshot.entry_id]
                ),
                version=OAUTH_CONFIG_ENTRY_VERSION,
            )

        await _reload_anchor(hass, plan)
        verify_migration_plan_result(hass, plan)
        _finish_anchor_data(hass, anchor, oauth_data, plan)
    except Exception as err:
        await rollback_migration_plan(hass, plan)
        raise MigrationExecutionError("NuHeat migration was rolled back") from err

    cleanup_failure = await _cleanup_plan_entries(hass, plan)
    if cleanup_failure is not None and not cleanup_failure.removed_entry_ids:
        await rollback_migration_plan(hass, plan)
        raise MigrationExecutionError("NuHeat cleanup failed before commit")

    if cleanup_failure is not None:
        _LOGGER.error("NuHeat migration cleanup is incomplete and will be retried")
        _create_repair_issue(hass, plan.anchor_entry_id, ISSUE_CLEANUP_INCOMPLETE)
        return MigrationResult(
            anchor_entry=anchor,
            removed_entry_ids=cleanup_failure.removed_entry_ids,
            pending_cleanup_entry_ids=cleanup_failure.pending_entry_ids,
            migrated_serials=plan.migrated_serials,
            cleanup_complete=False,
        )

    clean_data = dict(anchor.data)
    clean_data.pop(CONF_MIGRATION_STATE, None)
    clean_data.pop(CONF_MIGRATION_VALIDATED_SERIALS, None)
    hass.config_entries.async_update_entry(anchor, data=clean_data)
    _delete_repair_issue(hass, plan.anchor_entry_id, ISSUE_CLEANUP_INCOMPLETE)
    return MigrationResult(
        anchor_entry=anchor,
        removed_entry_ids=plan.redundant_entry_ids,
        pending_cleanup_entry_ids=(),
        migrated_serials=plan.migrated_serials,
        cleanup_complete=True,
    )


async def async_consolidate_legacy_entries(
    hass: HomeAssistant,
    initiating_entry: ConfigEntry[Any],
    *,
    oauth_data: dict[str, Any],
    account_unique_id: str,
    account_title: str,
    thermostats: list[Thermostat],
) -> MigrationResult:
    """Plan and execute a user-validated migration."""
    plan = build_migration_plan(
        hass,
        initiating_entry,
        account_unique_id=account_unique_id,
        account_title=account_title,
        thermostats=thermostats,
    )
    return await execute_migration_plan(hass, plan, oauth_data=oauth_data)


async def async_resume_migration_cleanup(
    hass: HomeAssistant, anchor: ConfigEntry[Any]
) -> None:
    """Converge an interrupted post-validation migration after restart."""
    if not is_migration_anchor(anchor):
        pending = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if is_pending_cleanup_entry(entry)
            and entry.data.get(CONF_MIGRATION_ANCHOR_ENTRY_ID) == anchor.entry_id
        ]
        if pending:
            _create_repair_issue(hass, anchor.entry_id, ISSUE_CLEANUP_INCOMPLETE)
        return

    raw_serials = anchor.data.get(CONF_MIGRATION_VALIDATED_SERIALS)
    if not isinstance(raw_serials, list) or not all(
        isinstance(serial, str) and serial for serial in raw_serials
    ):
        _create_repair_issue(hass, anchor.entry_id, ISSUE_CLEANUP_INCOMPLETE)
        return
    validated_serials = frozenset(raw_serials)

    try:
        coordinator_data = anchor.runtime_data.coordinator.data or {}
        _verify_validated_serials(validated_serials, coordinator_data)

        domain_entries = hass.config_entries.async_entries(DOMAIN)
        pending_entries = [
            entry
            for entry in domain_entries
            if is_pending_cleanup_entry(entry)
            and entry.data.get(CONF_MIGRATION_ANCHOR_ENTRY_ID) == anchor.entry_id
        ]
        legacy_entries = [
            entry
            for entry in domain_entries
            if is_legacy_entry(entry)
            and _legacy_serial(entry) in validated_serials
            and entry.entry_id != anchor.entry_id
        ]

        serial_entry_ids = tuple(
            (serial, entry.entry_id)
            for entry in legacy_entries
            if (serial := _legacy_serial(entry)) is not None
        )
        if serial_entry_ids:
            entities, devices = build_registry_snapshots(
                hass,
                serial_entry_ids=serial_entry_ids,
                anchor_entry_id=anchor.entry_id,
            )
            transfer_registry_ownership(
                hass,
                anchor_entry_id=anchor.entry_id,
                entity_snapshots=entities,
                device_snapshots=devices,
            )
            for entry in legacy_entries:
                serial = _legacy_serial(entry)
                assert serial is not None
                hass.config_entries.async_update_entry(
                    entry,
                    data=_pending_cleanup_data(anchor.entry_id, serial),
                    version=OAUTH_CONFIG_ENTRY_VERSION,
                )
            pending_entries.extend(legacy_entries)

        verify_registry_ownership(
            hass,
            anchor_entry_id=anchor.entry_id,
            serial_numbers=validated_serials,
        )
        for entry in pending_entries:
            if hass.config_entries.async_get_entry(entry.entry_id) is not None:
                await hass.config_entries.async_remove(entry.entry_id)
    except Exception:  # noqa: BLE001
        _LOGGER.error("NuHeat migration cleanup retry remains incomplete")
        _create_repair_issue(hass, anchor.entry_id, ISSUE_CLEANUP_INCOMPLETE)
        return

    clean_data = dict(anchor.data)
    clean_data.pop(CONF_USERNAME, None)
    clean_data.pop(CONF_PASSWORD, None)
    clean_data.pop(CONF_SERIAL_NUMBER, None)
    clean_data.pop(CONF_MIGRATION_STATE, None)
    clean_data.pop(CONF_MIGRATION_VALIDATED_SERIALS, None)
    hass.config_entries.async_update_entry(anchor, data=clean_data)
    _delete_repair_issue(hass, anchor.entry_id, ISSUE_CLEANUP_INCOMPLETE)
