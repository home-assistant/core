"""Tests for the Xiaomi BLE integration __init__ module."""

from __future__ import annotations

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
    """Test both legacy entities are renamed in the right order, without collision.

    "impedance_low" must move to "impedance_high" before the legacy
    "impedance" entity is moved onto "impedance_low", otherwise the second
    rename would collide with the (not yet renamed) first one.
    """
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


async def test_migrate_skipped_when_no_device_entry(hass: HomeAssistant) -> None:
    """Test the migration does nothing when the device is not yet known."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=S400_ADDRESS, version=1, minor_version=1
    )
    entry.add_to_hass(hass)

    # No device registered at all for this address: should not raise.
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
