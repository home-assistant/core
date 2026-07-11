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


def _async_setup_device(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry
) -> dr.DeviceEntry:
    """Create a device row for the given config entry."""
    return device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("bluetooth", S400_ADDRESS)},
        model="MJTZC01YM",
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


def _seed_restore_data(
    hass: HomeAssistant, entry: MockConfigEntry, data: dict | None = None
) -> dict:
    """Seed the real bluetooth passive-update-processor storage for entry."""
    processor_data = hass.data[PASSIVE_UPDATE_PROCESSOR]
    restore_data = data if data is not None else _stale_s400_restore_data()
    processor_data.all_restore_data[entry.entry_id] = restore_data
    return restore_data


# ---------------------------------------------------------------------------
# async_migrate_entry: unique_id renaming
# ---------------------------------------------------------------------------


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


async def test_migrate_leaves_generic_impedance_alone_without_low_signal(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a lone 'impedance' entity is left untouched.

    Only the S400 has ever emitted "impedance_low"; a device with a
    generic "impedance" entity and no "impedance_low" at all is a V1/V2
    scale's legitimate, still-live sensor and must never be renamed.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
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


# ---------------------------------------------------------------------------
# Restore-cache purge and phantom-entity cleanup, exercised through a full
# config entry setup against the real bluetooth passive-processor storage.
# ---------------------------------------------------------------------------


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
    device = _async_setup_device(device_registry, entry)
    # A genuine V1/V2 sensor: "impedance" only, never "impedance_low".
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
    _async_add_entity(
        entity_registry,
        entry,
        device.id,
        f"{S400_ADDRESS}-impedance_low",
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
