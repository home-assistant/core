"""Registry planning, transfer, verification, and rollback for NuHeat migration."""

from dataclasses import dataclass

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN


class RegistryMigrationError(RuntimeError):
    """Registry ownership could not be transferred safely."""


@dataclass(frozen=True, slots=True)
class EntityAssociationSnapshot:
    """Original entity association for one validated thermostat serial."""

    serial_number: str
    entity_id: str | None
    expected_entry_id: str | None
    original_config_entry_id: str | None


@dataclass(frozen=True, slots=True)
class DeviceAssociationSnapshot:
    """Original device associations for one validated thermostat serial."""

    serial_number: str
    device_id: str | None
    expected_entry_id: str | None
    original_config_entry_ids: frozenset[str]


def build_registry_snapshots(
    hass: HomeAssistant,
    *,
    serial_entry_ids: tuple[tuple[str, str | None], ...],
    anchor_entry_id: str,
) -> tuple[
    tuple[EntityAssociationSnapshot, ...], tuple[DeviceAssociationSnapshot, ...]
]:
    """Preflight all registry ownership without changing any record."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entity_snapshots: list[EntityAssociationSnapshot] = []
    device_snapshots: list[DeviceAssociationSnapshot] = []

    for serial_number, expected_entry_id in serial_entry_ids:
        entity_id = entity_registry.async_get_entity_id(
            CLIMATE_DOMAIN, DOMAIN, serial_number
        )
        entity = entity_registry.async_get(entity_id) if entity_id else None
        allowed_entry_ids = {anchor_entry_id}
        if expected_entry_id is not None:
            allowed_entry_ids.add(expected_entry_id)
        if entity is not None and entity.config_entry_id not in allowed_entry_ids:
            raise RegistryMigrationError(
                "NuHeat entity belongs to an unrelated config entry"
            )
        entity_snapshots.append(
            EntityAssociationSnapshot(
                serial_number=serial_number,
                entity_id=entity.entity_id if entity else None,
                expected_entry_id=expected_entry_id,
                original_config_entry_id=entity.config_entry_id if entity else None,
            )
        )

        device = device_registry.async_get_device(identifiers={(DOMAIN, serial_number)})
        if device is not None:
            if (DOMAIN, serial_number) not in device.identifiers:
                raise RegistryMigrationError(
                    "NuHeat device is missing its expected identifier"
                )
            if not device.config_entries.issubset(allowed_entry_ids):
                raise RegistryMigrationError(
                    "NuHeat device belongs to an unrelated config entry"
                )
        device_snapshots.append(
            DeviceAssociationSnapshot(
                serial_number=serial_number,
                device_id=device.id if device else None,
                expected_entry_id=expected_entry_id,
                original_config_entry_ids=(
                    frozenset(device.config_entries) if device else frozenset()
                ),
            )
        )

    return tuple(entity_snapshots), tuple(device_snapshots)


def validate_registry_snapshots(
    hass: HomeAssistant,
    entity_snapshots: tuple[EntityAssociationSnapshot, ...],
    device_snapshots: tuple[DeviceAssociationSnapshot, ...],
) -> None:
    """Verify registry state has not changed since preflight."""
    entity_registry = er.async_get(hass)
    for entity_snapshot in entity_snapshots:
        current_id = entity_registry.async_get_entity_id(
            CLIMATE_DOMAIN, DOMAIN, entity_snapshot.serial_number
        )
        if current_id != entity_snapshot.entity_id:
            raise RegistryMigrationError(
                "NuHeat entity registry changed after preflight"
            )
        if current_id is not None:
            entity = entity_registry.async_get(current_id)
            if (
                entity is None
                or entity.config_entry_id != entity_snapshot.original_config_entry_id
            ):
                raise RegistryMigrationError(
                    "NuHeat entity ownership changed after preflight"
                )

    device_registry = dr.async_get(hass)
    for device_snapshot in device_snapshots:
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, device_snapshot.serial_number)}
        )
        if (device.id if device else None) != device_snapshot.device_id:
            raise RegistryMigrationError(
                "NuHeat device registry changed after preflight"
            )
        if device is not None and frozenset(device.config_entries) != (
            device_snapshot.original_config_entry_ids
        ):
            raise RegistryMigrationError(
                "NuHeat device ownership changed after preflight"
            )


def transfer_registry_ownership(
    hass: HomeAssistant,
    *,
    anchor_entry_id: str,
    entity_snapshots: tuple[EntityAssociationSnapshot, ...],
    device_snapshots: tuple[DeviceAssociationSnapshot, ...],
) -> None:
    """Transfer existing records to the anchor without recreating them."""
    entity_registry = er.async_get(hass)
    for entity_snapshot in entity_snapshots:
        if (
            entity_snapshot.entity_id is None
            or entity_snapshot.expected_entry_id is None
        ):
            continue
        entity = entity_registry.async_get(entity_snapshot.entity_id)
        if entity is None:
            raise RegistryMigrationError("NuHeat entity disappeared during transfer")
        if entity.config_entry_id == entity_snapshot.expected_entry_id:
            entity_registry.async_update_entity(
                entity.entity_id, config_entry_id=anchor_entry_id
            )
        elif entity.config_entry_id != anchor_entry_id:
            raise RegistryMigrationError(
                "NuHeat entity ownership changed during transfer"
            )

    device_registry = dr.async_get(hass)
    for device_snapshot in device_snapshots:
        if (
            device_snapshot.device_id is None
            or device_snapshot.expected_entry_id is None
        ):
            continue
        device = device_registry.async_get(device_snapshot.device_id)
        if (
            device is None
            or (DOMAIN, device_snapshot.serial_number) not in device.identifiers
        ):
            raise RegistryMigrationError("NuHeat device disappeared during transfer")
        if device_snapshot.expected_entry_id in device.config_entries:
            # Current Home Assistant tracks config-entry and config-subentry
            # associations together. Add and remove in separate calls so the
            # second operation starts from the registry's newly stored state.
            device = device_registry.async_update_device(
                device.id,
                add_config_entry_id=anchor_entry_id,
            )
            if device is None:
                raise RegistryMigrationError("NuHeat device ownership add failed")
            device = device_registry.async_update_device(
                device.id, remove_config_entry_id=device_snapshot.expected_entry_id
            )
        if device is None or device.config_entries != {anchor_entry_id}:
            raise RegistryMigrationError(
                "NuHeat device ownership transfer did not converge"
            )


def verify_registry_ownership(
    hass: HomeAssistant,
    *,
    anchor_entry_id: str,
    serial_numbers: frozenset[str],
) -> None:
    """Verify every validated thermostat is exposed by the anchor entry."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    for serial_number in serial_numbers:
        entity_id = entity_registry.async_get_entity_id(
            CLIMATE_DOMAIN, DOMAIN, serial_number
        )
        entity = entity_registry.async_get(entity_id) if entity_id else None
        if entity is None or entity.config_entry_id != anchor_entry_id:
            raise RegistryMigrationError(
                "NuHeat anchor did not expose every expected entity"
            )
        device = device_registry.async_get_device(identifiers={(DOMAIN, serial_number)})
        if device is None or anchor_entry_id not in device.config_entries:
            raise RegistryMigrationError(
                "NuHeat anchor did not expose every expected device"
            )


def restore_registry_snapshots(
    hass: HomeAssistant,
    entity_snapshots: tuple[EntityAssociationSnapshot, ...],
    device_snapshots: tuple[DeviceAssociationSnapshot, ...],
) -> None:
    """Restore original associations and remove records created during reload."""
    entity_registry = er.async_get(hass)
    for entity_snapshot in entity_snapshots:
        current_id = entity_registry.async_get_entity_id(
            CLIMATE_DOMAIN, DOMAIN, entity_snapshot.serial_number
        )
        if entity_snapshot.entity_id is None:
            if current_id is not None:
                entity_registry.async_remove(current_id)
            continue
        if current_id != entity_snapshot.entity_id:
            raise RegistryMigrationError(
                "NuHeat entity identity changed during rollback"
            )
        entity_registry.async_update_entity(
            entity_snapshot.entity_id,
            config_entry_id=entity_snapshot.original_config_entry_id,
        )

    device_registry = dr.async_get(hass)
    for device_snapshot in device_snapshots:
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, device_snapshot.serial_number)}
        )
        if device_snapshot.device_id is None:
            if device is not None:
                device_registry.async_remove_device(device.id)
            continue
        if device is None or device.id != device_snapshot.device_id:
            raise RegistryMigrationError(
                "NuHeat device identity changed during rollback"
            )

        for entry_id in (
            device_snapshot.original_config_entry_ids - device.config_entries
        ):
            updated = device_registry.async_update_device(
                device.id, add_config_entry_id=entry_id
            )
            if updated is None:
                raise RegistryMigrationError("NuHeat device rollback add failed")
            device = updated
        for entry_id in (
            device.config_entries - device_snapshot.original_config_entry_ids
        ):
            updated = device_registry.async_update_device(
                device.id, remove_config_entry_id=entry_id
            )
            if updated is None:
                raise RegistryMigrationError("NuHeat device rollback remove failed")
            device = updated

        if (
            frozenset(device.config_entries)
            != device_snapshot.original_config_entry_ids
        ):
            raise RegistryMigrationError(
                "NuHeat device rollback did not restore ownership"
            )
