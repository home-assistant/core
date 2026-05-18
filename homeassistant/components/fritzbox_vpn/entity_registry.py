"""Entity and device registry helpers for VPN connection lifecycle."""

from __future__ import annotations

import logging
import re

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, UNIQUE_ID_PREFIX, UNIQUE_ID_SUFFIXES
from .models import runtime_from_hass

_LOGGER = logging.getLogger(__name__)

_ENTITY_ID_OBJECT_ID_SUFFIX_RE = re.compile(r"^(.+)_(\d+)$")


def connection_uid_from_entity_unique_id(unique_id: str) -> str | None:
    """Connection UID from entity unique_id; None if not our format."""
    if not unique_id or not unique_id.startswith(UNIQUE_ID_PREFIX):
        return None
    rest = unique_id[len(UNIQUE_ID_PREFIX) :]
    for suffix in UNIQUE_ID_SUFFIXES:
        if rest.endswith("_" + suffix):
            return rest[: -len(suffix) - 1]
    return None


def resolve_current_uids(
    hass: HomeAssistant, entry_id: str
) -> tuple[set[str] | None, str | None]:
    """Current VPN UIDs from coordinator.data."""
    runtime = runtime_from_hass(hass, entry_id)
    if runtime is None:
        return (None, "integration_not_loaded")
    coordinator = runtime.coordinator
    if not coordinator or not hasattr(coordinator, "data") or coordinator.data is None:
        return (None, "coordinator_not_ready")
    current_uids = set(coordinator.data.keys()) if coordinator.data else set()
    return (current_uids, None)


def get_orphaned_entity_entries(
    hass: HomeAssistant,
    entry_id: str,
    current_uids: set[str] | None = None,
) -> tuple[list[er.RegistryEntry] | None, str | None]:
    """Entity entries whose VPN connection no longer exists on the Fritz!Box."""
    if current_uids is None:
        current_uids, error_key = resolve_current_uids(hass, entry_id)
        if error_key is not None:
            return (None, error_key)
    registry = er.async_get(hass)
    to_remove = []
    for entry in er.async_entries_for_config_entry(registry, entry_id):
        uid = connection_uid_from_entity_unique_id(entry.unique_id or "")
        if uid is not None and uid not in current_uids:
            to_remove.append(entry)
    return (to_remove, None)


def uids_from_entity_entries(entries: list[er.RegistryEntry]) -> set[str]:
    """Connection UIDs from entity registry entries."""
    uids: set[str] = set()
    for entry in entries:
        uid = connection_uid_from_entity_unique_id(entry.unique_id or "")
        if uid is not None:
            uids.add(uid)
    return uids


def entity_id_base(entity_id: str) -> str | None:
    """Base entity_id when object_id has numeric suffix (_2, _3, …)."""
    if not entity_id or "." not in entity_id:
        return None
    domain, object_id = entity_id.split(".", 1)
    match = _ENTITY_ID_OBJECT_ID_SUFFIX_RE.match(object_id)
    if not match:
        return None
    return f"{domain}.{match.group(1)}"


def entity_id_suffix_number(entity_id: str) -> int | None:
    """Numeric suffix from entity_id object_id (_2, _3, ...)."""
    if not entity_id or "." not in entity_id:
        return None
    _, object_id = entity_id.split(".", 1)
    match = _ENTITY_ID_OBJECT_ID_SUFFIX_RE.match(object_id)
    if not match:
        return None
    try:
        return int(match.group(2))
    except (TypeError, ValueError):
        return None


def get_entity_id_suffix_repairs(
    registry: er.EntityRegistry, entry_id: str
) -> list[tuple[er.RegistryEntry, str, bool]]:
    """Repair operations as (suffixed entry, base_entity_id, remove_base_first)."""
    all_entries = er.async_entries_for_config_entry(registry, entry_id)
    by_entity_id = {e.entity_id: e for e in all_entries}
    suffixed_by_base: dict[str, list[er.RegistryEntry]] = {}

    for entry in all_entries:
        base = entity_id_base(entry.entity_id)
        if not base:
            continue
        suffixed_by_base.setdefault(base, []).append(entry)

    result: list[tuple[er.RegistryEntry, str, bool]] = []
    for base_entity_id, suffixed_entries in suffixed_by_base.items():
        preferred = sorted(
            suffixed_entries,
            key=lambda e: (entity_id_suffix_number(e.entity_id) or 10_000, e.entity_id),
        )[0]
        base_entry = by_entity_id.get(base_entity_id)
        if base_entry and base_entry.id == preferred.id:
            continue

        if not base_entry and registry.async_get(base_entity_id) is None:
            result.append((preferred, base_entity_id, False))
            continue

        if base_entry and base_entry.config_entry_id == entry_id:
            result.append((preferred, base_entity_id, True))

    return result


def repair_entity_id_suffixes(
    hass: HomeAssistant, entry_id: str
) -> tuple[int, list[str]]:
    """Repair suffixed entity IDs (_2, _3, ...) to base IDs."""
    registry = er.async_get(hass)
    repairs = get_entity_id_suffix_repairs(registry, entry_id)
    messages: list[str] = []
    for suffixed_entry, base_entity_id, remove_base_first in repairs:
        try:
            if remove_base_first:
                registry.async_remove(base_entity_id)
            registry.async_update_entity(
                suffixed_entry.entity_id, new_entity_id=base_entity_id
            )
            messages.append(f"{suffixed_entry.entity_id} → {base_entity_id}")
            _LOGGER.info(
                "Repaired entity ID: %s → %s",
                suffixed_entry.entity_id,
                base_entity_id,
            )
        except Exception as err:
            _LOGGER.warning(
                "Failed to repair %s → %s: %s",
                suffixed_entry.entity_id,
                base_entity_id,
                err,
            )
    return (len(messages), messages)


def remove_orphaned_entities(
    hass: HomeAssistant,
    entry_id: str,
    entries: list[er.RegistryEntry],
    *,
    remove_from_registry: bool = True,
) -> None:
    """Clear known_uids and optionally remove entity/device registry entries."""
    if not entries:
        return

    uids_removed = uids_from_entity_entries(entries)

    if remove_from_registry:
        entity_registry = er.async_get(hass)
        device_ids_affected = set()
        for entry in entries:
            if entry.device_id:
                device_ids_affected.add(entry.device_id)
            entity_registry.async_remove(entry.entity_id)
            _LOGGER.info(
                "Removed unavailable entity: %s (%s)",
                entry.entity_id,
                entry.unique_id,
            )

        device_registry = dr.async_get(hass)
        for uid in uids_removed:
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, entry_id, uid)}
            )
            if device:
                device_registry.async_remove_device(device.id)
                _LOGGER.info(
                    "Removed unavailable device for connection UID: %s (device_id: %s)",
                    uid,
                    device.id,
                )
                device_ids_affected.discard(device.id)

        for dev_id in device_ids_affected:
            device = device_registry.async_get(dev_id)
            if not device:
                continue
            if not er.async_entries_for_device(entity_registry, dev_id):
                device_registry.async_remove_device(dev_id)
                _LOGGER.info(
                    "Removed empty device (no entities left): %s (device_id: %s)",
                    device.name_by_user or device.name,
                    dev_id,
                )

    runtime = runtime_from_hass(hass, entry_id)
    if not uids_removed or runtime is None:
        return
    runtime.clear_known_uids(uids_removed)
