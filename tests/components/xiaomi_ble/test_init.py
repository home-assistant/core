"""Tests for the Xiaomi BLE integration __init__ module."""

from __future__ import annotations

from homeassistant.components.bluetooth.passive_update_processor import (
    PASSIVE_UPDATE_PROCESSOR,
)
from homeassistant.components.xiaomi_ble import (
    DATA_S400_IMPEDANCE_CACHE_PURGED,
    _async_purge_phantom_s400_impedance_entity,
    _async_purge_stale_s400_impedance_restore_cache,
)
from homeassistant.components.xiaomi_ble.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

S400_ADDRESS = "04:AE:47:67:C6:7C"
S400_MODEL = "MJTZC01YM"
NON_S400_MODEL = "XMTZC02HM/XMTZC05HM/NUN4049CN"


def _async_setup_device(
    device_registry: dr.DeviceRegistry,
    entry: MockConfigEntry,
    *,
    model: str = S400_MODEL,
) -> dr.DeviceEntry:
    """Create a device for the given config entry."""
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


async def test_migrate_renames_legacy_impedance_to_low(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the legacy generic 'impedance' entity is renamed to 'impedance_low'."""
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
    assert after.unique_id == f"{S400_ADDRESS}-impedance_low"
    assert after.previous_unique_id == f"{S400_ADDRESS}-impedance"
    # The rename must never disable the entity: history must stay attached.
    assert after.disabled_by is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_renames_impedance_low_to_high(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the legacy 'impedance_low' entity is renamed to 'impedance_high'."""
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
    assert after.disabled_by is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_full_chain_no_collision(
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

    low_after = entity_registry.async_get(low_entity_id)
    assert low_after is not None
    assert low_after.unique_id == f"{S400_ADDRESS}-impedance_high"

    # The two entities must remain distinct: no unique_id collision.
    assert legacy_after.entity_id != low_after.entity_id
    assert legacy_after.unique_id != low_after.unique_id

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_preserves_user_disabled_reason(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a user-disabled legacy entity keeps its disable reason when renamed.

    The migration must not override a disable reason set by someone else
    (e.g. the user manually disabling the entity) with its own, nor skip
    the rename just because the entity happens to be disabled.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
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


async def test_migrate_bumps_minor_version(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the config entry minor_version is bumped after migration."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    _async_setup_device(device_registry, entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 2

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_skipped_for_non_s400_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the legacy impedance entity is left untouched for non-S400 scales."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=NON_S400_MODEL)
    entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.unique_id == f"{S400_ADDRESS}-impedance"
    assert after.disabled_by is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_skipped_when_no_legacy_entity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the migration does nothing when there is no legacy entity to rename."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    _async_setup_device(device_registry, entry)

    # No legacy entity registered: should not raise, but minor_version
    # still gets bumped so the migration never runs again.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_defers_when_no_device_entry(hass: HomeAssistant) -> None:
    """Test the migration defers to a later restart when device is unknown.

    Marking the migration done without having been able to check the
    device model would risk permanently skipping a legitimate rename for
    an S400 whose device row simply wasn't restored yet.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)

    # No device registered at all for this address: should not raise,
    # and must not advance minor_version so this is retried later.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_migrate_already_done_is_noop(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup does not re-run the migration for an already-migrated entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
    # Simulate an entity that already has the final, correct unique_id.
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
    # Must be left alone: no further rename since minor_version is current.
    assert after.unique_id == f"{S400_ADDRESS}-impedance_low"
    assert after.previous_unique_id is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_phantom_skipped_when_migration_not_complete(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the phantom cleanup never touches a not-yet-migrated entity.

    If async_migrate_entry deferred the rename (e.g. the device row
    wasn't known yet), minor_version stays at 1 and the legacy
    "-impedance" entity is still the genuine, not-yet-migrated one -- not
    a phantom. It must survive even once the device becomes known within
    the same setup.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
    genuine_entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )

    _async_purge_phantom_s400_impedance_entity(hass, entry)

    assert entity_registry.async_get(genuine_entity_id) is not None


async def test_purge_phantom_removes_orphan_impedance_entity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a phantom legacy 'impedance' entity is removed on every setup.

    This simulates what happens on an instance that used to have the
    legacy generic "impedance" entity: the bluetooth passive-update
    processor's own restore cache (separate from the entity registry)
    still remembers that key and recreates an empty entity for it right
    after platform setup, even though the migration already renamed the
    real one away in a previous run.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry)
    # Simulate the phantom entity reappearing with the legacy unique_id.
    phantom_entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(phantom_entity_id) is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_phantom_skipped_for_non_s400_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the phantom cleanup leaves the entity alone for non-S400 scales."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    device = _async_setup_device(device_registry, entry, model=NON_S400_MODEL)
    entity_id = _async_add_entity(
        entity_registry, entry, device.id, f"{S400_ADDRESS}-impedance"
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_phantom_noop_when_absent(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the phantom cleanup does nothing when there is no orphan entity."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    _async_setup_device(device_registry, entry)

    # No legacy/phantom entity registered: should not raise.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


class _FakeCoordinator:
    """Minimal stand-in exposing only what the cache purge needs."""

    def __init__(self, restore_data: dict) -> None:
        self.restore_data = restore_data


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


async def test_purge_stale_restore_cache_through_full_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the stale cache is purged via a real config entry setup.

    Unlike the tests above, this seeds Bluetooth's own
    passive-update-processor restore storage (rather than calling the
    private helper with a fake coordinator) and runs a full config entry
    setup, to prove the purge actually happens before the sensor
    platform's processor registration consumes that storage -- not just
    that the helper's logic is correct in isolation.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    _async_setup_device(device_registry, entry)

    # Seed the real bluetooth passive-update-processor restore storage,
    # shaped like a pre-fix S400 cache dump, for this entry.
    processor_data = hass.data[PASSIVE_UPDATE_PROCESSOR]
    processor_data.all_restore_data[entry.entry_id] = _stale_s400_restore_data()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sensor_data = processor_data.all_restore_data[entry.entry_id][Platform.SENSOR]
    assert "impedance___" not in sensor_data["entity_data"]
    assert "impedance_low___" not in sensor_data["entity_data"]
    # The correctly labeled impedance_high value must survive.
    assert sensor_data["entity_data"]["impedance_high___"] == 497.6

    # No phantom entity should have been created from the (now purged)
    # stale "impedance" description.
    entity_registry = er.async_get(hass)
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{S400_ADDRESS}-impedance"
        )
        is None
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_purge_stale_restore_cache_removes_impedance_keys(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test stale impedance/impedance_low restore cache entries are dropped."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    _async_setup_device(device_registry, entry)

    restore_data = _stale_s400_restore_data()
    coordinator = _FakeCoordinator(restore_data)

    _async_purge_stale_s400_impedance_restore_cache(hass, entry, coordinator)

    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance___" not in sensor_data["entity_data"]
    assert "impedance___" not in sensor_data["entity_descriptions"]
    assert "impedance_low___" not in sensor_data["entity_data"]
    assert "impedance_low___" not in sensor_data["entity_descriptions"]

    # Unrelated keys, including the correctly labeled impedance_high,
    # must be left untouched.
    assert sensor_data["entity_data"]["impedance_high___"] == 497.6
    assert sensor_data["entity_data"]["mass___"] == 74.2

    assert entry.data[DATA_S400_IMPEDANCE_CACHE_PURGED] is True


async def test_purge_stale_restore_cache_runs_once(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the purge does not run again once the marker is set.

    Once real, correctly labeled data has repopulated the cache, a second
    purge pass must not discard it.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=S400_ADDRESS,
        version=1,
        minor_version=2,
        data={DATA_S400_IMPEDANCE_CACHE_PURGED: True},
    )
    entry.add_to_hass(hass)
    _async_setup_device(device_registry, entry)

    restore_data = _stale_s400_restore_data()
    coordinator = _FakeCoordinator(restore_data)

    _async_purge_stale_s400_impedance_restore_cache(hass, entry, coordinator)

    # Marker was already set: the (here deliberately still-stale-looking)
    # entries must be left alone, since real data may look identical in
    # shape to what a fresh advertisement would have written.
    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance___" in sensor_data["entity_data"]
    assert "impedance_low___" in sensor_data["entity_data"]


async def test_purge_stale_restore_cache_skipped_for_non_s400_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the cache purge leaves non-S400 scales' data untouched."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    _async_setup_device(device_registry, entry, model=NON_S400_MODEL)

    restore_data = _stale_s400_restore_data()
    coordinator = _FakeCoordinator(restore_data)

    _async_purge_stale_s400_impedance_restore_cache(hass, entry, coordinator)

    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance___" in sensor_data["entity_data"]
    assert "impedance_low___" in sensor_data["entity_data"]
    # The marker is still recorded, to avoid re-checking every restart.
    assert entry.data[DATA_S400_IMPEDANCE_CACHE_PURGED] is True


async def test_purge_stale_restore_cache_defers_when_no_device_entry(
    hass: HomeAssistant,
) -> None:
    """Test the cache purge defers when the device row is not yet known.

    Marking the purge done without having been able to check the device
    model would risk permanently skipping a legitimate S400's stale
    cache entries.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=2
    )
    entry.add_to_hass(hass)
    # No device registered at all for this address.

    restore_data = _stale_s400_restore_data()
    coordinator = _FakeCoordinator(restore_data)

    _async_purge_stale_s400_impedance_restore_cache(hass, entry, coordinator)

    sensor_data = restore_data[Platform.SENSOR]
    assert "impedance___" in sensor_data["entity_data"]
    assert "impedance_low___" in sensor_data["entity_data"]
    # Must NOT be marked done, so this is retried on the next setup.
    assert DATA_S400_IMPEDANCE_CACHE_PURGED not in entry.data
