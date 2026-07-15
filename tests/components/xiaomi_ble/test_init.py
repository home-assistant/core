"""Tests for the Xiaomi BLE integration __init__ module."""

from __future__ import annotations

from homeassistant.components.bluetooth.passive_update_processor import (
    PASSIVE_UPDATE_PROCESSOR,
)
from homeassistant.components.xiaomi_ble.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

S400_ADDRESS = "04:AE:47:67:C6:7C"
DATA_S400_IMPEDANCE_CACHE_PURGED = "s400_impedance_restore_cache_purged"
DATA_S400_CONFIRMED_AT_MIGRATION = "s400_confirmed_at_migration"
S400_MODEL = "MJTZC01YM"
V1V2_MODEL = "XMTZC02HM/XMTZC05HM/NUN4049CN"


def _async_setup_device(
    device_registry: dr.DeviceRegistry,
    entry: MockConfigEntry,
    *,
    model: str = S400_MODEL,
) -> dr.DeviceEntry:
    """Create a device row for the given config entry."""
    return device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("bluetooth", S400_ADDRESS)},
        model=model,
        name="Body Composition Scale C67C",
    )


def _async_add_entity(
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    device_id: str,
    unique_id: str,
    *,
    original_name: str = "Impedance",
    disabled_by: er.RegistryEntryDisabler | None = None,
) -> str:
    """Create a sensor entity with the given unique_id and return its entity_id."""
    entry_entity = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        unique_id,
        config_entry=entry,
        device_id=device_id,
        original_name=original_name,
    )
    if disabled_by is not None:
        entry_entity = entity_registry.async_update_entity(
            entry_entity.entity_id, disabled_by=disabled_by
        )
    return entry_entity.entity_id


def _stale_s400_restore_data() -> dict:
    """Build restore_data shaped like a pre-fix S400 cache dump."""
    return {
        Platform.SENSOR: {
            "entity_data": {
                "impedance___": 535.3,
                "impedance_low___": 479.3,
                "impedance_high___": 497.6,
                "mass___": 74.2,
            },
            "entity_descriptions": {
                "impedance___": {"key": "impedance_ohm"},
                "impedance_low___": {"key": "impedance_low"},
                "impedance_high___": {"key": "impedance_high"},
                "mass___": {"key": "mass_kg"},
            },
            "entity_names": {},
            "devices": {},
        }
    }


def _v1v2_restore_data() -> dict:
    """Build restore_data shaped like a real V1/V2 cache dump.

    Unlike the S400, a V1/V2 scale's library parser never emits
    "impedance_low"/"impedance_high" at all -- only the generic
    "impedance" key -- so its restore cache never contains those.
    """
    return {
        Platform.SENSOR: {
            "entity_data": {
                "impedance___": 428.0,
                "mass___": 68.5,
            },
            "entity_descriptions": {
                "impedance___": {"key": "impedance_ohm"},
                "mass___": {"key": "mass_kg"},
            },
            "entity_names": {},
            "devices": {},
        }
    }


def _fresh_s400_restore_data() -> dict:
    """Build restore_data shaped like a genuinely fresh, never-buggy S400.

    A device that only ever ran the corrected library never has the
    generic "impedance" key at all -- only "impedance_low"/"_high",
    correctly labeled from the start.
    """
    return {
        Platform.SENSOR: {
            "entity_data": {
                "impedance_low___": 479.3,
                "impedance_high___": 497.6,
                "mass___": 74.2,
            },
            "entity_descriptions": {
                "impedance_low___": {"key": "impedance_low"},
                "impedance_high___": {"key": "impedance_high"},
                "mass___": {"key": "mass_kg"},
            },
            "entity_names": {},
            "devices": {},
        }
    }


def _seed_restore_data(
    hass: HomeAssistant, entry: MockConfigEntry, data: dict | None = None
) -> dict:
    """Seed the real bluetooth passive-update-processor storage for entry."""
    processor_data = hass.data[PASSIVE_UPDATE_PROCESSOR]
    restore_data = data if data is not None else _stale_s400_restore_data()
    processor_data.all_restore_data[entry.entry_id] = restore_data
    return restore_data


async def test_migrate_renames_both_legacy_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test both legacy entities are renamed without a unique-ID collision."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
    legacy_entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )
    low_entity_id = _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    legacy_after = entity_registry.async_get(legacy_entity_id)
    assert legacy_after is not None
    assert legacy_after.unique_id == f"{S400_ADDRESS}-impedance_low"
    assert legacy_after.previous_unique_id == f"{S400_ADDRESS}-impedance"
    assert legacy_after.disabled_by is None

    low_after = entity_registry.async_get(low_entity_id)
    assert low_after is not None
    assert low_after.unique_id == f"{S400_ADDRESS}-impedance_high"
    assert low_after.previous_unique_id == f"{S400_ADDRESS}-impedance_low"

    assert legacy_after.entity_id != low_after.entity_id
    assert legacy_after.unique_id != low_after.unique_id

    assert entry.minor_version == 2

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_renames_impedance_low_only(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test 'impedance_low' alone is renamed to 'impedance_high'."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
    entity_id = _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.unique_id == f"{S400_ADDRESS}-impedance_high"
    assert after.previous_unique_id == f"{S400_ADDRESS}-impedance_low"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_leaves_generic_impedance_alone_for_v1v2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a V1/V2 scale's lone 'impedance' entity is left untouched."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=V1V2_MODEL)
    entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.unique_id == f"{S400_ADDRESS}-impedance"
    assert after.previous_unique_id is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_renames_generic_impedance_via_device_registry_fallback(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an S400 that only ever has 'impedance' is still renamed.

    The old parser could emit the generic "impedance" key without
    "impedance_low" if a device never received the second advertisement
    before the upgrade. The device registry, when already available, is
    the fallback that catches this case.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=S400_MODEL)
    entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.unique_id == f"{S400_ADDRESS}-impedance_low"
    assert after.previous_unique_id == f"{S400_ADDRESS}-impedance"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_fallback_noop_when_device_also_unknown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the device-registry fallback doesn't error with no device row.

    If neither the entity-registry signal nor the device registry can
    identify this as an S400, the lone "impedance" entity is left alone
    -- same outcome as the V1/V2 case, just via a different reason.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    # No device row at all for this address.

    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{S400_ADDRESS}-impedance",
        config_entry=entry,
        original_name="Impedance",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{S400_ADDRESS}-impedance"
    )
    assert after is not None

    assert entry.minor_version == 2

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_preserves_user_disabled_reason(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a user-disabled legacy entity keeps its disable reason when renamed."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
    _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )
    entity_id = _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance",
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.unique_id == f"{S400_ADDRESS}-impedance_low"
    assert after.previous_unique_id == f"{S400_ADDRESS}-impedance"
    assert after.disabled_by is er.RegistryEntryDisabler.USER

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_skipped_when_no_legacy_entity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the migration still completes when there is nothing to rename."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    _async_setup_device(device_registry, entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_already_done_is_noop(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup does not re-run the migration for an already-migrated entry.

    This is also the regression case for a fresh S400 that had no
    entities at its very first migration pass (which immediately bumped
    minor_version to 2) and only got its correctly-named entities from a
    live advertisement afterwards: a later restart must never attempt to
    rename them again.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
    entity_id = _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.unique_id == f"{S400_ADDRESS}-impedance_low"
    assert after.previous_unique_id is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_stale_restore_cache_after_low_only_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the cache purge still identifies an S400 after a low-only rename.

    A migration that only had "impedance_low" to rename moves it onto
    "impedance_high", so by the time the cache purge runs right after,
    no "impedance_low" entity exists yet. It must still recognize this
    as an S400 via "impedance_high" instead, or the purge (and its
    one-time marker) would be skipped for a real S400.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
    _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )
    restore_data = _seed_restore_data(hass, entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance___" not in sensor_data["entity_data"]
    assert "impedance_low___" not in sensor_data["entity_data"]
    assert entry.data[DATA_S400_IMPEDANCE_CACHE_PURGED] is True

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_stale_restore_cache_via_cache_signal_alone(
    hass: HomeAssistant,
) -> None:
    """Test the cache purge still identifies an S400 with no registry entities.

    If the user deleted the S400's entities entirely while stale cache
    data remained, there is no entity-registry signal left at all. The
    restore cache's own descriptions must still be enough to identify
    this as an S400 and purge the stale keys.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    # No device, no entities: only the restore cache still has S400 data.
    restore_data = _seed_restore_data(hass, entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance___" not in sensor_data["entity_data"]
    assert "impedance_low___" not in sensor_data["entity_data"]
    assert entry.data[DATA_S400_IMPEDANCE_CACHE_PURGED] is True

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


def _low_only_stale_restore_data() -> dict:
    """Build restore_data for a device whose old history is low-only.

    The old parser wrote only the "impedance_low" key (no generic
    "impedance") for a device that only ever got the advertisement
    carrying that key -- so there's no legacy-residue signal to prove
    staleness, only migration provenance can.
    """
    return {
        Platform.SENSOR: {
            "entity_data": {
                "impedance_low___": 479.3,
                "mass___": 74.2,
            },
            "entity_descriptions": {
                "impedance_low___": {"key": "impedance_low"},
                "mass___": {"key": "mass_kg"},
            },
            "entity_names": {},
            "devices": {},
        }
    }


async def test_purge_stale_restore_cache_via_low_only_provenance(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the stale low-only cache is purged via migration provenance.

    No generic "impedance" key ever existed for this device, so its
    presence can't prove staleness here. async_migrate_entry persists
    DATA_S400_CONFIRMED_AT_MIGRATION at the moment of that specific rename,
    proving it instead.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=S400_MODEL)
    _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )
    restore_data = _seed_restore_data(hass, entry, _low_only_stale_restore_data())

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.data[DATA_S400_CONFIRMED_AT_MIGRATION] is True
    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance_low___" not in sensor_data["entity_data"]
    assert entry.data[DATA_S400_IMPEDANCE_CACHE_PURGED] is True

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_stale_restore_cache_low_only_marker_survives_entity_deletion(
    hass: HomeAssistant,
) -> None:
    """Test the persisted low-only marker purges even with no entities left.

    If the user deletes the renamed "impedance_high" entity after a
    low-only migration, its previous_unique_id (the only other proof)
    is lost with it. The independently persisted
    DATA_S400_CONFIRMED_AT_MIGRATION marker must still be enough to purge the
    stale cached value on a later setup.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=S400_ADDRESS,
        version=1,
        minor_version=2,
        data={DATA_S400_CONFIRMED_AT_MIGRATION: True},
    )
    entry.add_to_hass(hass)
    # No device, no entities: as if everything was deleted after the
    # original migration, leaving only the persisted marker behind.
    restore_data = _seed_restore_data(hass, entry, _low_only_stale_restore_data())

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance_low___" not in sensor_data["entity_data"]
    assert entry.data[DATA_S400_IMPEDANCE_CACHE_PURGED] is True

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_marks_confirmed_when_entities_deleted_before_upgrade(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test migration marks a device confirmed via model alone.

    If both "-impedance" and "-impedance_low" were deleted before ever
    upgrading, there's no entity-registry signal left at migration time
    at all. The device-registry model fallback must still fire (not
    gated on a legacy entity existing) so DATA_S400_CONFIRMED_AT_MIGRATION
    gets persisted, letting a later purge clean up any residue the
    bluetooth cache still holds.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    _async_setup_device(device_registry, entry, model=S400_MODEL)
    # No entities at all: as if everything was deleted before upgrading.
    restore_data = _seed_restore_data(hass, entry, _low_only_stale_restore_data())

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.data[DATA_S400_CONFIRMED_AT_MIGRATION] is True
    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance_low___" not in sensor_data["entity_data"]
    assert entry.data[DATA_S400_IMPEDANCE_CACHE_PURGED] is True

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_stale_restore_cache_leaves_fresh_s400_untouched(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a fresh S400's already-correct impedance_low is never purged.

    A device that never ran the buggy library has no generic
    "impedance" key in its cache at all -- only that key's presence is
    proof of pre-fix data. Without it, "impedance_low" already holds a
    real, correctly labeled value and must survive, even once the
    device is confirmed as an S400 and the marker is set.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=S400_MODEL)
    _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )
    restore_data = _seed_restore_data(hass, entry, _fresh_s400_restore_data())

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sensor_data = restore_data[Platform.SENSOR]
    assert sensor_data["entity_data"]["impedance_low___"] == 479.3
    assert sensor_data["entity_data"]["impedance_high___"] == 497.6
    assert entry.data[DATA_S400_IMPEDANCE_CACHE_PURGED] is True

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_stale_restore_cache_through_full_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the stale cache is purged and no phantom entity survives setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
    _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )
    restore_data = _seed_restore_data(hass, entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance___" not in sensor_data["entity_data"]
    assert "impedance_low___" not in sensor_data["entity_data"]
    # The correctly labeled impedance_high value must survive.
    assert sensor_data["entity_data"]["impedance_high___"] == 497.6

    assert entry.data[DATA_S400_IMPEDANCE_CACHE_PURGED] is True

    # No phantom entity should have been created from the (now purged)
    # stale "impedance" description.
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{S400_ADDRESS}-impedance"
        )
        is None
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_stale_restore_cache_retryable_when_model_unknown(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device with no model set yet is not treated as confirmed non-S400.

    device_entry.model can be None (not yet populated). Treating that as
    "confirmed something else" would permanently skip a real S400 whose
    model just hasn't been recorded yet.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("bluetooth", S400_ADDRESS)},
        name="Body Composition Scale C67C",
        # model intentionally omitted / None
    )

    restore_data = _seed_restore_data(hass, entry, _v1v2_restore_data())

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance___" in sensor_data["entity_data"]
    assert DATA_S400_IMPEDANCE_CACHE_PURGED not in entry.data

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_stale_restore_cache_leaves_non_s400_data_untouched(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a V1/V2 scale's legitimate cached 'impedance' value is untouched.

    Without an "impedance_low" entity to prove this is an S400, the cache
    purge (and the phantom cleanup) must leave a device's data alone.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=V1V2_MODEL)
    entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )
    restore_data = _seed_restore_data(hass, entry, _v1v2_restore_data())

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance___" in sensor_data["entity_data"]

    # The marker is still recorded, to avoid re-checking every restart.
    assert entry.data[DATA_S400_IMPEDANCE_CACHE_PURGED] is True

    # The genuine V1/V2 entity must survive, untouched.
    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.unique_id == f"{S400_ADDRESS}-impedance"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_stale_restore_cache_runs_once(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the purge does not run again once the marker is already set.

    Once real, correctly labeled data has repopulated the cache, a
    second purge pass must not discard it.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=S400_ADDRESS,
        version=1,
        minor_version=2,
        data={DATA_S400_IMPEDANCE_CACHE_PURGED: True},
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
    _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )
    restore_data = _seed_restore_data(hass, entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Marker was already set: these (here deliberately still-stale-looking)
    # entries must be left alone, since real data may look identical in
    # shape to what a fresh advertisement would have written.
    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance___" in sensor_data["entity_data"]
    assert "impedance_low___" in sensor_data["entity_data"]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_recover_interrupted_migration_leaves_ambiguous_pair_alone(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test recovery leaves both entities alone when "impedance_low" exists.

    A lingering "-impedance" plus an existing "-impedance_low" is
    structurally identical whether that low entity is the original one
    awaiting promotion to "impedance_high", or an already-correct one
    that happens to coexist with a "-impedance" resurrected by an
    unrelated save-timing race (see _async_recover_interrupted_s400_migration).
    Recovery must not guess and leave both alone.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=S400_MODEL)
    legacy_entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )
    low_entity_id = _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    legacy_after = entity_registry.async_get(legacy_entity_id)
    assert legacy_after is not None
    assert legacy_after.unique_id == f"{S400_ADDRESS}-impedance"

    low_after = entity_registry.async_get(low_entity_id)
    assert low_after is not None
    assert low_after.unique_id == f"{S400_ADDRESS}-impedance_low"

    assert legacy_after.unique_id != low_after.unique_id

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_recover_interrupted_migration_completes_remaining_step(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test recovery finishes the second step if only the first landed.

    Simulates a crash after "-impedance_low" -> "-impedance_high" reached
    disk but before "-impedance" -> "-impedance_low" did: only the
    second, still-pending step must run.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=S400_MODEL)
    entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )
    # Simulate the already-completed first step with the high unique ID.
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{S400_ADDRESS}-impedance_high",
        config_entry=entry,
        device_id=device.id,
        original_name="Impedance High",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.unique_id == f"{S400_ADDRESS}-impedance_low"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_recover_interrupted_migration_noop_when_already_done(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test recovery does nothing once the migration is genuinely complete."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=S400_MODEL)
    entity_id = _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.unique_id == f"{S400_ADDRESS}-impedance_low"
    assert after.previous_unique_id is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_recover_interrupted_migration_skipped_for_v1v2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test recovery never touches a V1/V2 scale's legitimate entity."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=V1V2_MODEL)
    entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.unique_id == f"{S400_ADDRESS}-impedance"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_phantom_spares_legacy_entity_with_native_high(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a native "impedance_high" alone never proves "-impedance" is a phantom.

    The corrected library can create "impedance_high" natively from live
    data, independent of any rename. A genuine, still-un-recovered
    legacy "-impedance" entity coexisting with it (the exact pair
    _async_recover_interrupted_s400_migration deliberately leaves alone)
    must survive -- only "impedance_low".previous_unique_id proves a
    rename actually happened.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=S400_MODEL)
    legacy_entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )
    _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )
    _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_high",
        original_name="Impedance High",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(legacy_entity_id)
    assert after is not None
    assert after.unique_id == f"{S400_ADDRESS}-impedance"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_phantom_removes_entity_despite_purge_marker(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the phantom-entity safety net still catches a stale description.

    This is the defense-in-depth path: the primary defense is the cache
    purge running before the sensor platform consumes restore_data, but
    if that step is skipped (marker already set) and a stale description
    is present regardless, the resulting phantom entity must still be
    removed rather than linger in the UI.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=S400_ADDRESS,
        version=1,
        minor_version=2,
        data={DATA_S400_IMPEDANCE_CACHE_PURGED: True},
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
    real_entity_id = _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance",
        original_name="Impedance",
    )
    entity_registry.async_update_entity(
        real_entity_id,
        new_unique_id=f"{S400_ADDRESS}-impedance_low",
        original_name="Impedance Low",
    )
    _seed_restore_data(hass, entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{S400_ADDRESS}-impedance"
        )
        is None
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
