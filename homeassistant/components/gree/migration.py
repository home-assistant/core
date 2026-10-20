"""Split legacy Gree registry ownership without contacting devices."""

import asyncio
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.hass_dict import HassKey

from .const import CONF_IDENTIFIER, DOMAIN
from .discovery import normalize_identifier
from .switch import GREE_SWITCHES

_MIGRATION_LOCK: HassKey[asyncio.Lock] = HassKey("gree_migration_lock")
_SOURCE = "_migration_source_entry_id"
_SWITCH_SUFFIXES = tuple(f"_{description.key}" for description in GREE_SWITCHES)


@dataclass
class _Group:
    """An existing physical identity and its exact registry records."""

    raw_identifiers: set[str] = field(default_factory=set)
    devices: list[dr.DeviceEntry] = field(default_factory=list)
    entities: list[er.RegistryEntry] = field(default_factory=list)
    child: ConfigEntry | None = None

    @property
    def raw_identifier(self) -> str:
        """Return the preflight-validated spelling."""
        return next(iter(self.raw_identifiers))


def _canonical(identifier: object) -> str:
    """Reject invalid durable identities without modifying registries."""
    if not isinstance(identifier, str):
        raise HomeAssistantError(f"Invalid legacy Gree identifier: {identifier!r}")
    try:
        return normalize_identifier(identifier)
    except (TypeError, ValueError) as err:
        raise HomeAssistantError(
            f"Invalid legacy Gree identifier: {identifier!r}"
        ) from err


def _entity_identifier(entity: er.RegistryEntry) -> str:
    """Recover only the exact identity forms created by the Gree platforms."""
    if (
        entity.platform != DOMAIN
        or entity.config_subentry_id is not None
        or not isinstance(entity.unique_id, str)
    ):
        raise HomeAssistantError(f"Unsupported legacy Gree entity: {entity.entity_id}")
    if entity.domain == "climate":
        return entity.unique_id
    if entity.domain == "switch":
        for suffix in _SWITCH_SUFFIXES:
            if entity.unique_id.endswith(suffix):
                return entity.unique_id.removesuffix(suffix)
    raise HomeAssistantError(f"Unsupported legacy Gree entity: {entity.entity_id}")


def _device_identifiers(device: dr.DeviceEntry) -> set[str]:
    """Prefer Gree identifiers over network connection identifiers."""
    identifiers = {value for domain, value in device.identifiers if domain == DOMAIN}
    return identifiers or {
        value for kind, value in device.connections if kind == dr.CONNECTION_NETWORK_MAC
    }


def _validate_group_identity(
    identifier: str, group: _Group, entries: list[ConfigEntry], source_id: str
) -> None:
    """Reject conflicting spellings, device links, and destination ownership."""
    if len(group.raw_identifiers) != 1:
        raise HomeAssistantError(f"Ambiguous raw Gree identity for {identifier}")
    for candidate in entries:
        if candidate.entry_id == source_id or candidate.version == 1:
            continue
        if (
            candidate.unique_id is not None
            and _canonical(candidate.unique_id) == identifier
        ):
            if candidate is not group.child:
                raise HomeAssistantError(
                    f"Gree identity {identifier} already has another entry"
                )


@callback
def _inventory(hass: HomeAssistant, source_id: str) -> dict[str, _Group]:
    """Validate the entire source and all previously created destinations."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    entries = hass.config_entries.async_entries(DOMAIN)
    children = [entry for entry in entries if entry.data.get(_SOURCE) == source_id]
    owners = {source_id, *(entry.entry_id for entry in children)}
    groups: dict[str, _Group] = {}
    child_identifiers: dict[str, str] = {}
    for child in children:
        identifier = _canonical(child.data.get(CONF_IDENTIFIER))
        if child.version != 2 or child.unique_id != identifier:
            raise HomeAssistantError(
                f"Invalid Gree migration destination: {child.entry_id}"
            )
        group = groups.setdefault(identifier, _Group())
        if group.child is not None:
            raise HomeAssistantError(
                f"Duplicate Gree migration destination for {identifier}"
            )
        group.child = child
        group.raw_identifiers.add(child.data[CONF_IDENTIFIER])
        child_identifiers[child.entry_id] = identifier

    devices: dict[str, dr.DeviceEntry] = {}
    for owner in owners:
        if dr.async_child_entries_for_config_entry(device_registry, owner):
            raise HomeAssistantError(
                "Legacy Gree child-device ownership is unsupported"
            )
        for device in dr.async_entries_for_config_entry(device_registry, owner):
            if (
                device.config_subentry_id is not None
                or dr.async_entries_for_parent_device(device_registry, device.id)
            ):
                raise HomeAssistantError(
                    "Legacy Gree child-device ownership is unsupported"
                )
            devices[device.id] = device
        for entity in er.async_entries_for_config_entry(entity_registry, owner):
            raw_identifier = _entity_identifier(entity)
            identifier = _canonical(raw_identifier)
            if owner in child_identifiers and child_identifiers[owner] != identifier:
                raise HomeAssistantError(
                    f"Gree destination owns another identity: {identifier}"
                )
            if entity.device_id is not None and (
                (linked_device := device_registry.async_get(entity.device_id)) is None
                or not isinstance(linked_device, dr.DeviceEntry)
                or linked_device.config_entry_id not in owners
            ):
                raise HomeAssistantError(
                    f"Unexpected Gree device ownership: {entity.entity_id}"
                )
            group = groups.setdefault(identifier, _Group())
            group.raw_identifiers.add(raw_identifier)
            group.entities.append(entity)

    for device in devices.values():
        linked_entities = er.async_entries_for_device(
            entity_registry, device.id, include_disabled_entities=True
        )
        raw_identifiers = {
            _entity_identifier(entity)
            for entity in linked_entities
            if entity.config_entry_id in owners
        }
        device_identifiers = {
            value for domain, value in device.identifiers if domain == DOMAIN
        }
        normalized_identifiers = {
            _canonical(raw_identifier)
            for raw_identifier in raw_identifiers | device_identifiers
        }
        if not raw_identifiers:
            raw_identifiers = _device_identifiers(device)
            normalized_identifiers = {
                _canonical(raw_identifier) for raw_identifier in raw_identifiers
            }
        if len(normalized_identifiers) != 1:
            raise HomeAssistantError(f"Ambiguous legacy Gree device: {device.id}")
        identifier = next(iter(normalized_identifiers))
        if (
            device.config_entry_id in child_identifiers
            and child_identifiers[device.config_entry_id] != identifier
        ):
            raise HomeAssistantError(
                f"Gree destination owns another device: {device.id}"
            )
        group = groups.setdefault(identifier, _Group())
        if group.devices:
            raise HomeAssistantError(f"Duplicate physical Gree device for {identifier}")
        group.devices.append(device)
        for entity in linked_entities:
            if (
                entity.config_entry_id not in owners
                or _canonical(_entity_identifier(entity)) != identifier
            ):
                raise HomeAssistantError(
                    f"Conflicting Gree device identity: {device.id}"
                )
        if not group.raw_identifiers:
            group.raw_identifiers.update(raw_identifiers)

    for identifier, group in groups.items():
        _validate_group_identity(identifier, group, entries, source_id)
    return groups


@callback
def _transfer(
    hass: HomeAssistant, group: _Group, source_id: str, target_id: str
) -> None:
    """Move entities first because device-move listeners run synchronously."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    for old_entity in group.entities:
        if (entity := entity_registry.async_get(old_entity.entity_id)) is not None and (
            entity.config_entry_id == source_id
        ):
            entity_registry.async_update_entity(
                entity.entity_id,
                config_entry_id=target_id,
                disabled_by=entity.disabled_by,
            )
    for old_device in group.devices:
        if (device := device_registry.async_get(old_device.id)) is not None and (
            device.config_entry_id == source_id
        ):
            device_registry.async_update_device(
                device.id,
                new_config_entry_id=target_id,
            )


@callback
def async_reconcile_migrated_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Finish an interrupted transfer before child setup can create entities."""
    if (source_id := entry.data.get(_SOURCE)) is None:
        return
    groups = _inventory(hass, source_id)
    identifier = _canonical(entry.data[CONF_IDENTIFIER])
    _transfer(hass, groups[identifier], source_id, entry.entry_id)


def _entry_data(group: _Group) -> dict[str, Any]:
    """Build offline device data without guessing a network address."""
    device = group.devices[0] if group.devices else None
    return {
        "host": None,
        "port": 7000,
        CONF_IDENTIFIER: group.raw_identifier,
        "name": device.name if device else None,
        "brand": None,
        "model": device.model if device else None,
        "version": device.sw_version if device else None,
        "mid": None,
    }


async def async_migrate_legacy_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Preflight and split a shared entry, preserving its representative."""
    lock = hass.data.setdefault(_MIGRATION_LOCK, asyncio.Lock())
    async with lock:
        if entry.version != 1:
            return
        groups = _inventory(hass, entry.entry_id)
        if not groups:
            hass.async_create_task(
                hass.config_entries.async_remove(entry.entry_id),
                f"Remove empty legacy Gree entry {entry.entry_id}",
            )
            return
        representatives = [
            identifier
            for identifier, group in groups.items()
            if group.child is None
            and (
                any(
                    device.config_entry_id == entry.entry_id for device in group.devices
                )
                or any(
                    entity.config_entry_id == entry.entry_id
                    for entity in group.entities
                )
            )
        ]
        if not representatives:
            raise HomeAssistantError(
                "Legacy Gree source has no remaining representative"
            )
        representative = min(representatives)
        for identifier in sorted(groups):
            if identifier == representative:
                continue
            group = groups[identifier]
            child = group.child
            if child is None:
                device = group.devices[0] if group.devices else None
                child = ConfigEntry(
                    domain=DOMAIN,
                    version=2,
                    minor_version=1,
                    unique_id=identifier,
                    source=SOURCE_IMPORT,
                    title=(device.name_by_user or device.name or group.raw_identifier)
                    if device
                    else group.raw_identifier,
                    data={**_entry_data(group), _SOURCE: entry.entry_id},
                    options=entry.options,
                    pref_disable_new_entities=entry.pref_disable_new_entities,
                    pref_disable_polling=entry.pref_disable_polling,
                    discovery_keys=MappingProxyType({}),
                    subentries_data=(),
                )
                await hass.config_entries.async_add(child)
            async_reconcile_migrated_entry(hass, child)
        hass.config_entries.async_update_entry(
            entry,
            version=2,
            minor_version=1,
            unique_id=representative,
            data=_entry_data(groups[representative]),
        )


@callback
def async_get_legacy_identifiers(hass: HomeAssistant) -> set[str]:
    """Reserve identities of all unmigrated entries, including disabled ones."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    normalized_identifiers: set[str] = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.version != 1:
            continue
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            for raw_identifier in _device_identifiers(device):
                try:
                    normalized_identifiers.add(_canonical(raw_identifier))
                except HomeAssistantError:
                    continue
        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            try:
                normalized_identifiers.add(_canonical(_entity_identifier(entity)))
            except HomeAssistantError:
                continue
    return normalized_identifiers
